from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional
import mido
from collections import deque
from util import Int4

class MidiEncoderError(Exception):
    """Base exception for MidiEncoder errors"""
    pass

class PatternError(MidiEncoderError):
    """Raised when there's an issue with the pattern"""
    pass

class NibbleProcessingError(MidiEncoderError):
    """Raised when there's an issue processing nibbles"""
    pass

class NibbleTarget(Enum):
    CHANNEL = 'c'
    NOTE = 'n'
    VELOCITY = 'v'
    TIMING = 't'
    LENGTH = 'l'

@dataclass
class Remainder:
    bits: str  # Binary representation of unused nibbles
    pattern_position: int  # Position in pattern where we stopped
    
    def __str__(self):
        return f"Unused bits: {self.bits} (stopped at position {self.pattern_position} in pattern)"

@dataclass(frozen=True)
class MessageComponent:
    message_id: int  # Identifies which message this component belongs to
    component_type: NibbleTarget
    value: int
    
    def __hash__(self):
        return hash((self.message_id, self.component_type))
    
    def __eq__(self, other):
        if not isinstance(other, MessageComponent):
            return False
        return (self.message_id == other.message_id and 
                self.component_type == other.component_type)

class MidiEncoder:
    def __init__(self, pattern: str = "cnvtl"):
        valid_chars = set('cnvtl')
        if not pattern or not all(c in valid_chars for c in pattern):
            raise PatternError("Pattern must only contain characters: c,n,v,t,l")
        self.pattern = pattern
        
    def encode_chunk(self, nibbles: deque[Int4]) -> Tuple[List[Tuple[mido.Message, mido.Message]], Optional[Remainder]]:
        if not nibbles:
            raise NibbleProcessingError("No nibbles to process")
        
        components = set()
        message_id = 0
        pattern_length = len(self.pattern)
        
        # Process one pattern iteration at a time
        while len(nibbles) >= pattern_length:
            current_nibbles = [nibbles.popleft() for _ in range(pattern_length)]
            new_components = self._create_message_components(current_nibbles, message_id)
            components.update(new_components)
            message_id += 1
        
        # Create messages from complete component sets
        messages = self._create_message_pairs_from_components(components)
        
        # Calculate remainder
        remainder = None
        if nibbles:
            remainder_bits = ''.join([format(int(n), '04b') for n in nibbles])
            remainder = Remainder(
                bits=remainder_bits,
                pattern_position=len(components) % len(self.pattern)
            )
        
        return messages, remainder
        
    def _create_message_components(self, pattern_nibbles: List[Int4], message_id: int) -> set[MessageComponent]:
        components = set()
        
        for i, nibble in enumerate(pattern_nibbles):
            target = NibbleTarget(self.pattern[i])
            
            # Find existing component for this target and message_id
            existing = next((c for c in components 
                            if c.message_id == message_id and c.component_type == target), None)
            
            if existing is not None:
                # Update existing component (shift and combine nibbles)
                new_value = (existing.value << 4) | int(nibble)
                components.remove(existing)
                components.add(MessageComponent(message_id, target, new_value))
            else:
                # Create new component
                components.add(MessageComponent(message_id, target, int(nibble)))
        
        return components
        
    def _create_message_pairs_from_components(self, components: set[MessageComponent]) -> List[Tuple[mido.Message, mido.Message]]:
        messages = []
        message_ids = {c.message_id for c in components}
        
        for mid in sorted(message_ids):
            msg_components = {c for c in components if c.message_id == mid}
            
            # Check if we have all required components
            if all(NibbleTarget(t) in {c.component_type for c in msg_components} 
                   for t in 'cnvtl'):
                # Get component values
                params = {c.component_type: c.value for c in msg_components}
                
                note_on = mido.Message('note_on',
                                     channel=min(params[NibbleTarget.CHANNEL], 15),
                                     note=min(params[NibbleTarget.NOTE], 127),
                                     velocity=min(params[NibbleTarget.VELOCITY], 127),
                                     time=params[NibbleTarget.TIMING])
                
                note_off = mido.Message('note_off',
                                      channel=min(params[NibbleTarget.CHANNEL], 15),
                                      note=min(params[NibbleTarget.NOTE], 127),
                                      velocity=0,
                                      time=self._calculate_note_length(params[NibbleTarget.LENGTH]))
                
                messages.append((note_on, note_off))
        
        return messages
        
    def _calculate_note_length(self, length_value: int) -> int:
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
        return note_durations.get(length_value, 1) 