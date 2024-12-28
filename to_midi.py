import os
import mido
import argparse

from util import Int4 
from collections import deque

PPQN = 480
TEMPO = 120

def main(args: argparse.Namespace) -> None:
    """
    Converts binary data into MIDI format.

    Args:
        args (argparse.Namespace): Command line arguments.
    """
    file_path = args.file_path
    output_path = args.output_file
    chunk_size = args.chunk_size 
    max_chunks = args.max_chunks

    if not os.path.isfile(file_path):
        print(f"File {file_path} does not exist.")
        return

    data = read_file_as_bytes(file_path)
    max_chunks = len(data) // chunk_size if max_chunks == -1 else max_chunks
    chunks = chunk_data(data, chunk_size, max_chunks)

    messages = []
    active_notes = set()
    while len(chunks) > 0:
        # one nibble for channel, two each for note and velocity, two nibbles for note on time, one nibble for note length
        chunk_group = deque([chunks.popleft() for _ in range(8)])
        note_on_message, note_off_message = create_midi_message(chunk_group)

        messages.append(note_on_message)
        messages.append(note_off_message)
        print_human_readable_midi(note_on_message)
        print_human_readable_midi(note_off_message)

    create_midi_file(messages, output_path)

def read_file_as_bytes(file_path: str) -> bytes:
    """
    Reads a file and returns its content as bytes.

    Args:
        file_path (str): Path to the file.

    Returns:
        bytes: Content of the file.
    """
    with open(file_path, 'rb') as file:
        return file.read()

def split_byte_to_nibbles(value: int) -> tuple:
    """
    Splits a byte into two 4-bit nibbles.

    Args:
        value (int): The byte value to split.

    Returns:
        tuple: A tuple containing two 4-bit nibbles.
    """
    # Mask the lowest 8 bits.
    # 0xFF = 255 = 11111111
    value &= 0xFF

    # Extract right 4 bits
    lower_bits = Int4(value & 0xF)

    # Bitshift right to extract the left 4 bits
    upper_bits = Int4((value >> 4) & 0xF)

    return upper_bits, lower_bits

def join_nibbles_to_int(nibbles: deque) -> bytes:
    """
    Joins two 4-bit nibbles into a single byte.

    Args:
        nibbles (deque): A deque containing two 4-bit nibbles.

    Returns:
        bytes: A single byte.
    """
    return nibbles.popleft().to_bytes()[0] | nibbles.popleft().to_bytes()[0]

def chunk_data(data: bytes, chunk_size: int, num_chunks: int) -> deque:
    """
    Chunks the data into smaller pieces by converting each 8-bit integer byte into two 4-bit nibbles.

    Args:
        data (bytes): The data to be chunked and converted.
        chunk_size (int): The size of each chunk.
        num_chunks (int): The maximum number of chunks.

    Returns:
        deque: A deque of tuples, each containing two 4-bit nibbles.
    """
    # Enforce max number of chunks
    num_chunks = num_chunks if num_chunks < len(data) else len(data)
    data = data[:num_chunks * chunk_size]

    # Split the list of bytes into nibbles
    nibbles = deque(
        z
        for x, y in (split_byte_to_nibbles(byte) for byte in data)
        for z in (x, y)
    )

    return nibbles

def create_midi_message(chunk_group: deque) -> mido.Message:
    """
    Creates a MIDI message from a group of nibbles.

    Args:
        chunk_group (deque): A deque of nibbles representing a MIDI message.

    Returns:
        mido.Message: A MIDI message object.

    Note-On Message:
    - Status Byte: 1001cccc (where cccc is the MIDI channel number, 0-15)
    - Data Byte 1: 0nnnnnnn (where nnnnnnn is the note number, 0-127)
    - Data Byte 2: 0vvvvvvv (where vvvvvvv is the velocity, 0-127)

    Note-Off Message:
    - Status Byte: 1000nnnn (where nnnn is the MIDI channel number, 0-15)
    - Data Byte 1: 0kkkkkkk (where kkkkkkk is the note number, 0-127)
    - Data Byte 2: 0vvvvvvv (where vvvvvvv is the release velocity, 0-127)

    Example Note-On Message (Channel 1, Note C4, Velocity 64):
    - Status Byte: 10010000 (0x90)
    - Data Byte 1: 00111100 (0x3C, Note C4)
    - Data Byte 2: 01000000 (0x40, Velocity 64)

    Example Note-Off Message (Channel 1, Note C4, Velocity 64):
    - Status Byte: 10000000 (0x80)
    - Data Byte 1: 00111100 (0x3C, Note C4)
    - Data Byte 2: 01000000 (0x40, Velocity 64)

    Note:
    - The most significant bit (MSB) of each byte is used to distinguish status bytes (MSB = 1) from data bytes (MSB = 0).
    - The channel number is encoded in the lower nibble of the status byte.
    """
    # Initialize an empty deque to store the message
    message_components = deque()

    # The note-on status byte is 0x90
    # The first nibble of the chunk is the channel number
    message_components.append(b'\x90')
    message_components.append(chunk_group.popleft().to_bytes())

    # The next two bytes (four nibbles) are the note and velocity
    for _ in range(4):
        message_components.append(chunk_group.popleft().to_bytes())

    # Convert deque to bytes for mido.Message
    message_bytes = []
    while len(message_components) > 1:
        # We OR every two nibbles to get the full bytes
        # The [0] is to get the first (and only) byte from the bytearray.
        # Python does not like to OR bytes directly.
        message_bytes.append(
            (message_components.popleft()[0] | message_components.popleft()[0]).to_bytes()
        )
    message_bytes = b''.join(message_bytes)

    note_on_message = mido.Message.from_bytes(message_bytes)

    # The remaining 2 nibbles are the timing information
    # Set note-on time
    timing = create_timing(chunk_group)
    note_on_message.time = timing[0]

    # Create note-off message and set time
    note_off_message = mido.Message('note_off', channel=note_on_message.channel, note=note_on_message.note, velocity=0)
    note_off_message.time = timing[1]

    return note_on_message, note_off_message

def create_timing(nibbles: deque, ppqn: int=PPQN) -> float:
    """
    Creates timing information from nibbles.

    Args:
        nibbles (deque): A deque of nibbles representing timing information.
        ppqn (int, optional): Pulses per quarter note. Defaults to PPQN.

    Returns:
        float: Real time in milliseconds.
    """
    # Use the first byte of each chunk for timing
    note_on_time = join_nibbles_to_int(nibbles)
    note_length = nibbles.popleft().to_bytes()[0]

    # Convert delta time to real time (in milliseconds) based on a tempo
    ms_per_tick = (60000 / TEMPO) / ppqn
    note_on_time = note_on_time * ms_per_tick

    # Map note_length to musical note durations in terms of quarter notes
    note_durations = {
        0: 1,      # quarter note
        1: 0.75,   # dotted eighth note
        2: 0.5,    # eighth note
        3: 0.375,  # dotted sixteenth note
        4: 0.25,   # sixteenth note
        5: 0.1875, # triplet sixteenth note
        6: 0.125,  # thirty-second note
        7: 0.09375,# triplet thirty-second note
        8: 0.0625, # sixty-fourth note
        9: 0.046875,# triplet sixty-fourth note
        10: 0.03125,# one hundred twenty-eighth note
        11: 0.0234375,# triplet one hundred twenty-eighth note
        12: 0.015625,# two hundred fifty-sixth note
        13: 0.01171875,# triplet two hundred fifty-sixth note
        14: 0.0078125,# five hundred twelfth note
        15: 0.005859375,# triplet five hundred twelfth note
    }

    # Get the duration as a proportion of a quarter note
    note_duration_quarter_notes = note_durations[note_length]

    # Calculate the duration in milliseconds based on the tempo (bpm)
    ms_per_quarter_note = 60000 / TEMPO
    note_duration_ms = note_duration_quarter_notes * ms_per_quarter_note

    # Calculate the note-off time
    note_off_time = note_on_time + note_duration_ms

    return int(note_on_time), int(note_off_time)    

def print_human_readable_midi(midi_message: mido.Message) -> None:
    """
    Prints a human-readable representation of a MIDI message.

    Args:
        midi_message (mido.Message): The MIDI message to print.
        timing (float): The timing information in milliseconds.
    """
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    note_name = note_names[midi_message.note % 12] + str(midi_message.note // 12 - 1)

    if midi_message.type == 'note_on' and midi_message.velocity > 0:
        message_type = "note-on"
    elif midi_message.type == 'note_off' or (midi_message.type == 'note_on' and midi_message.velocity == 0):
        message_type = "note-off"
    else:
        message_type = "unknown"

    print(f"{message_type} {note_name} : velocity {midi_message.velocity} : delta t {midi_message.time:.2f} ms")

def create_midi_file(messages: list, output_path: str) -> None:
    """
    Creates a MIDI file from a list of messages.

    Args:
        messages (list): A list of tuples containing MIDI messages and their timing.
        output_path (str): Path to save the MIDI file.
    """
    midi_file = mido.MidiFile()
    track = mido.MidiTrack()
    midi_file.tracks.append(track)

    for message in messages:
        track.append(message)

    # Add end of track message
    track.append(mido.MetaMessage('end_of_track'))

    midi_file.save(output_path)
    print(f"MIDI file saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process binary data to MIDI")
    parser.add_argument("file_path", help="Path to the input binary file")
    parser.add_argument("--output", choices=['print', 'file'], default='print', help="Output mode: print to console or save to file")
    parser.add_argument("--max_chunks", type=int, default=100, help="Number of chunks to process. Use -1 for all chunks")
    parser.add_argument("--output_file", help="Output MIDI file path (required if output mode is 'file')", default="out.mid")
    parser.add_argument("--chunk_size", type=int, default=4, help="Size of each chunk in bytes")

    args = parser.parse_args()

    if args.output == 'file' and not args.output_file:
        parser.error("--output-file is required when output mode is 'file'")

    main(args)
