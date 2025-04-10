import os
import sys
import argparse
import traceback
from music21 import converter, midi
import xml.etree.ElementTree as ET
import re

def remove_lyrics_from_mei(mei_data):
    """
    Remove all lyrics elements from MEI XML data and sanitize measure numbers
    
    Parameters:
    mei_data (str): The MEI XML content as a string
    
    Returns:
    str: The MEI XML with lyrics removed and measure numbers sanitized
    """
    try:
        # Parse the XML
        root = ET.fromstring(mei_data)
        
        # Define namespace (found in the root element)
        ns = {'mei': 'http://www.music-encoding.org/ns/mei'}
        
        # Handle syllable types that music21 might not understand
        for syl in root.findall('.//mei:syl', ns):
            wordpos = syl.get('wordpos')
            if wordpos in ['s', 'i', 'm', 't']:  # These are standard MEI values
                continue
            elif wordpos == 'u':  # Unknown/unclear
                syl.set('wordpos', 'i')  # Treat as intermediate
            else:
                syl.set('wordpos', 's')  # Default to single
        
        # Find and remove all verse elements (and their children)
        for verse in root.findall('.//mei:verse', ns):
            # Find parent note
            parent_note = None
            for ancestor in root.iter():
                if verse in list(ancestor):
                    parent_note = ancestor
                    break
            if parent_note is not None:
                parent_note.remove(verse)
        
        # Sanitize measure numbers
        for measure in root.findall('.//mei:measure', ns):
            measure_num = measure.get('n')
            if measure_num:
                try:
                    # Try to convert to integer
                    int(measure_num)
                except ValueError:
                    # If conversion fails, replace with a valid number
                    # Here we'll use the measure's position among its siblings
                    parent = None
                    for ancestor in root.iter():
                        if measure in list(ancestor):
                            parent = ancestor
                            break
                    if parent is not None:
                        sibling_measures = parent.findall('mei:measure', ns)
                        measure_index = sibling_measures.index(measure)
                        measure.set('n', str(measure_index))
        
        # Convert back to string
        return ET.tostring(root, encoding='utf-8').decode('utf-8')
    
    except Exception as e:
        print(f"Error processing MEI data: {str(e)}")
        traceback.print_exc()
        return mei_data  # Return original if processing failed

def convert_mei_to_midi(input_file, output_file=None):
    """
    Convert an MEI file to MIDI format using music21, after removing lyrics
    
    Parameters:
    input_file (str): Path to the MEI file
    output_file (str): Path to save the MIDI file. If None, replaces .mei with .mid
    
    Returns:
    str: Path to the output file if successful, None otherwise
    """
    try:
        # Generate default output path if none provided
        if output_file is None:
            output_file = os.path.splitext(input_file)[0] + '.mid'
        
        print(f"Converting {input_file} to MIDI...")
        
        # Read the MEI file
        with open(input_file, 'r', encoding='utf-8') as f:
            mei_data = f.read()
        
        # Remove lyrics
        mei_data_no_lyrics = remove_lyrics_from_mei(mei_data)
        
        # Write to a temporary file with .mei extension
        temp_file = input_file + '.temp.mei'
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(mei_data_no_lyrics)
        
        # Parse with music21
        try:
            score = converter.parse(temp_file, format='mei')
            
            # Create a new MIDI file manually to bypass repeat expansion
            try:
                mf = midi.MidiFile()
                mt = midi.MidiTrack(0)
                mf.tracks.append(mt)
                
                # Add tempo events if they exist
                for t in score.flat.getElementsByClass('TempoIndication'):
                    mt.events.append(midi.MidiEvent(
                        track=0,
                        time=0,
                        type='SET_TEMPO',
                        data=midi.translate.tempoToMidiEvents(t)[0].data
                    ))
                
                # Add all notes to the track
                for n in score.flat.notesAndRests:
                    # Skip rests for this simple conversion
                    if n.isRest:
                        continue
                        
                    # Convert note to MIDI events
                    for midi_note in midi.translate.noteToMidiEvents(n):
                        mt.events.append(midi_note)
                
                # Write the MIDI file
                mf.open(output_file, 'wb')
                mf.write()
                mf.close()
                
                print(f"Successfully converted to {output_file}")
                result = output_file
                
            except Exception as e:
                print(f"MIDI creation error: {str(e)}")
                traceback.print_exc()
                result = None
                
        except Exception as e:
            print(f"Music21 conversion error: {str(e)}")
            traceback.print_exc()
            result = None
        
        # Clean up temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        return result
    
    except Exception as e:
        print(f"Error processing {input_file}: {str(e)}")
        traceback.print_exc()
        return None

def process_directory(input_dir, output_dir=None):
    """
    Process all MEI files in a directory
    
    Parameters:
    input_dir (str): Directory containing MEI files
    output_dir (str): Directory to save MIDI files. If None, saves in the same directory
    
    Returns:
    int: Number of successfully converted files
    """
    if not os.path.isdir(input_dir):
        print(f"Error: {input_dir} is not a valid directory")
        return 0
    
    # Create output directory if needed
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    success_count = 0
    failed_count = 0
    
    # Process each MEI file in directory
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.mei'):
            input_path = os.path.join(input_dir, filename)
            
            if output_dir:
                output_filename = os.path.splitext(filename)[0] + '.mid'
                output_path = os.path.join(output_dir, output_filename)
            else:
                output_path = None  # Will use default naming in convert function
            
            result = convert_mei_to_midi(input_path, output_path)
            if result:
                success_count += 1
            else:
                failed_count += 1
    
    print(f"Conversion complete: {success_count} succeeded, {failed_count} failed")
    return success_count

def main():
    parser = argparse.ArgumentParser(description='Convert MEI files to MIDI after removing lyrics')
    parser.add_argument('input', help='Input MEI file or directory containing MEI files')
    parser.add_argument('-o', '--output', help='Output MIDI file or directory (optional)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose error output')
    
    args = parser.parse_args()
    
    if os.path.isdir(args.input):
        # Process directory
        count = process_directory(args.input, args.output)
        print(f"Converted {count} files successfully")
    elif os.path.isfile(args.input) and args.input.lower().endswith('.mei'):
        # Process single file
        convert_mei_to_midi(args.input, args.output)
    else:
        print("Error: Input must be an MEI file or a directory containing MEI files")
        sys.exit(1)

if __name__ == "__main__":
    main()
