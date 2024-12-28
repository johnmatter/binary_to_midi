import os
import mido
import argparse

from util import Int4 
from collections import deque
from midi_encoder import MidiEncoder

PPQN = 480
TEMPO = 120

def main(args: argparse.Namespace) -> None:
    """
    Converts binary data into MIDI format.

    Args:
        args (argparse.Namespace): Command line arguments.
    """
    try:
        encoder = MidiEncoder(args.pattern)
    except PatternError as e:
        print(f"Error with pattern '{args.pattern}': {e}")
        return
        
    try:
        data = read_file_as_bytes(args.file_path)
    except FileNotFoundError:
        print(f"Error: File '{args.file_path}' not found")
        return
    except IOError as e:
        print(f"Error reading file: {e}")
        return
        
    messages = []
    try:
        chunks = chunk_data(data, args.chunk_size, args.max_chunks)
        print(f"Created {len(chunks)} nibbles from input file")
        
        while chunks:
            try:
                print(f"\nProcessing chunk with {len(chunks)} nibbles remaining...")
                message_pairs, remainder = encoder.encode_chunk(chunks)
                
                for note_on, note_off in message_pairs:
                    messages.extend([note_on, note_off])
                    if args.output == 'print':
                        print_human_readable_midi(note_on)
                        print_human_readable_midi(note_off)
                        
                if remainder:
                    print(f"Remainder found: {remainder}")
                    break
                    
            except NibbleProcessingError as e:
                print(f"Error processing nibbles: {e}")
                break
                
    except Exception as e:
        print(f"Unexpected error: {e}")
        return
        
    if args.output == 'file' and messages:
        try:
            create_midi_file(messages, args.output_file)
        except IOError as e:
            print(f"Error saving MIDI file: {e}")

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
    parser.add_argument("--pattern", help="Pattern string for nibble assignment", default="cnvtl")

    args = parser.parse_args()

    if args.output == 'file' and not args.output_file:
        parser.error("--output-file is required when output mode is 'file'")

    main(args)
