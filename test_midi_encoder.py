import pytest
from collections import deque
from midi_encoder import (
    MidiEncoder, 
    PatternError, 
    NibbleProcessingError, 
    Remainder,
    NibbleTarget
)
from util import Int4

@pytest.fixture
def encoder():
    return MidiEncoder("cnvtl")

@pytest.fixture
def complex_encoder():
    return MidiEncoder("cnvltcnvlt")

def create_test_nibbles(values):
    return deque(Int4(v) for v in values)

@pytest.mark.parametrize("pattern,valid", [
    ("cnvtl", True),
    ("cnvcnvtltl", True),
    ("", False),
    ("invalid", False),
    ("cnvtlx", False),
])
def test_pattern_validation(pattern, valid):
    if valid:
        encoder = MidiEncoder(pattern)
        assert encoder.pattern == pattern
    else:
        with pytest.raises(PatternError):
            MidiEncoder(pattern)

@pytest.mark.parametrize("nibble_values,expected_messages", [
    ([0,                    # channel
      3, 12,               # note (60 split into nibbles)
      4, 0,                # velocity (64 split into nibbles)
      0, 1,                # timing (two nibbles)
      0], 1),              # length
    ([0,                    # first channel
      3, 12,               # first note (60)
      4, 0,                # first velocity (64)
      0, 1,                # first timing
      0,                   # first length
      1,                   # second channel
      3, 14,               # second note (62)
      4, 0,                # second velocity (64)
      0, 1,                # second timing
      0], 2),              # second length
    ([0, 3, 12], 0),       # Incomplete note
])
def test_message_creation(encoder, nibble_values, expected_messages):
    nibbles = create_test_nibbles(nibble_values)
    messages, remainder = encoder.encode_chunk(nibbles)
    assert len(messages) == expected_messages

def test_empty_input(encoder):
    with pytest.raises(NibbleProcessingError, match="No nibbles to process"):
        encoder.encode_chunk(deque())

@pytest.mark.parametrize("channel,note,velocity", [
    (0, 60, 64),    # Middle values
    (15, 127, 127), # Max values
    (0, 0, 0),      # Min values
])
def test_parameter_ranges(encoder, channel, note, velocity):
    # Split multi-nibble values
    note_high = note >> 4
    note_low = note & 0xF
    vel_high = velocity >> 4
    vel_low = velocity & 0xF
    
    nibbles = create_test_nibbles([
        channel,
        note_high, note_low,  # Two nibbles for note
        vel_high, vel_low,    # Two nibbles for velocity
        0  # length
    ])
    messages, _ = encoder.encode_chunk(nibbles)
    note_on, _ = messages[0]
    
    assert note_on.channel == channel
    assert note_on.note == note
    assert note_on.velocity == velocity

def test_remainder_creation(encoder):
    # Incomplete pattern
    nibbles = create_test_nibbles([0, 60, 64])
    _, remainder = encoder.encode_chunk(nibbles)
    
    assert remainder is not None
    assert remainder.pattern_position == 3  # Position after 'v' in pattern
    assert len(remainder.bits) == 12  # 3 nibbles * 4 bits

@pytest.mark.parametrize("pattern,nibble_values,expected_messages", [
    ("cnvltcnv", [
        0,                    # channel
        3, 12,               # note (60 split into nibbles)
        4, 0,                # velocity (64 split into nibbles)
        0, 1,                # timing
        0,                   # length
        1,                   # next channel
        3, 14,               # next note (62 split into nibbles)
        4, 0                 # next velocity (64 split into nibbles)
    ], 1),  # One complete, one partial
    ("cnvcnvtltl", [
        0,                    # first channel
        3, 12,               # first note (60)
        4, 0,                # first velocity (64)
        1,                    # second channel
        3, 14,               # second note (62)
        4, 0,                # second velocity (64)
        0, 1,                # timing
        0, 0                 # length
    ], 2),  # Two interleaved
])
def test_complex_patterns(pattern, nibble_values, expected_messages):
    encoder = MidiEncoder(pattern)
    nibbles = create_test_nibbles(nibble_values)
    messages, remainder = encoder.encode_chunk(nibbles)
    assert len(messages) == expected_messages

def test_timing_calculation(encoder):
    # Test different timing values with two nibbles
    for timing in range(16):
        high_nibble = timing >> 4
        low_nibble = timing & 0xF
        nibbles = create_test_nibbles([0, 60, 64, high_nibble, low_nibble, 0])
        messages, _ = encoder.encode_chunk(nibbles)
        note_on, _ = messages[0]
        assert note_on.time == timing

def test_note_length_mapping(encoder):
    # Test different note lengths
    for length in range(16):
        nibbles = create_test_nibbles([0, 60, 64, 0, length])
        messages, _ = encoder.encode_chunk(nibbles)
        _, note_off = messages[0]
        assert note_off.time > 0  # Actual values defined in _calculate_note_length