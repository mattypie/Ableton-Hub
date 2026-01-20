"""Examine the LiveSet's global scale information."""

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path

def examine_liveset_scale(als_path: Path):
    """Examine the LiveSet's global scale information."""
    print(f"Examining: {als_path}")
    print("=" * 80)
    
    with gzip.open(als_path, 'rb') as f:
        xml_data = f.read()
    
    root = ET.fromstring(xml_data)
    
    # Find LiveSet element
    liveset = None
    for elem in root.iter():
        if elem.tag == 'LiveSet':
            liveset = elem
            break
    
    if liveset is None:
        print("ERROR: LiveSet element not found!")
        return
    
    print("\n=== LiveSet Element ===")
    print(f"Tag: {liveset.tag}")
    print(f"Attributes: {liveset.attrib}")
    
    # Look for ScaleInformation directly under LiveSet
    print("\n=== Direct Children of LiveSet ===")
    for child in list(liveset)[:20]:  # First 20 children
        print(f"  {child.tag}: {child.attrib}")
        if 'Scale' in child.tag or 'Key' in child.tag or 'InKey' in child.tag:
            print(f"    *** SCALE-RELATED ***")
            # Show all sub-children
            for subchild in child:
                print(f"      {subchild.tag}: {subchild.attrib}")
                for subsubchild in subchild:
                    print(f"        {subsubchild.tag}: {subsubchild.attrib}")
    
    # Specifically look for ScaleInformation
    print("\n=== ScaleInformation Element ===")
    scale_info = None
    for child in liveset:
        if child.tag == 'ScaleInformation':
            scale_info = child
            break
    
    if scale_info is not None:
        print(f"Found ScaleInformation!")
        print(f"Attributes: {scale_info.attrib}")
        print(f"Children:")
        for child in scale_info:
            print(f"  {child.tag}: {child.attrib}")
            if child.text:
                print(f"    Text: {child.text}")
    else:
        print("ScaleInformation not found directly under LiveSet")
        # Search more broadly
        print("\nSearching for ScaleInformation anywhere...")
        for elem in liveset.iter():
            if elem.tag == 'ScaleInformation':
                print(f"Found ScaleInformation at depth {len(list(elem.iterancestors()))}")
                print(f"  Attributes: {elem.attrib}")
                print(f"  Children:")
                for child in elem:
                    print(f"    {child.tag}: {child.attrib}")
                break
    
    # Look for InKey element
    print("\n=== InKey Element ===")
    inkey = None
    for child in liveset:
        if child.tag == 'InKey':
            inkey = child
            break
    
    if inkey is not None:
        print(f"Found InKey!")
        print(f"Attributes: {inkey.attrib}")
    else:
        print("InKey not found directly under LiveSet")
    
    # Check for scale name mapping
    print("\n=== Scale Name Mapping ===")
    print("Looking for scale name definitions...")
    # Scale names in Ableton are typically numeric IDs mapped to names
    # 0 = Major, 1 = Minor, etc.
    scale_name_map = {
        '0': 'Major',
        '1': 'Minor',
        '2': 'Dorian',
        '3': 'Mixolydian',
        '4': 'Lydian',
        '5': 'Phrygian',
        '6': 'Locrian',
        '7': 'Diminished',
        '8': 'Whole Half',
        '9': 'Whole Tone',
        '10': 'Minor Blues',
        '11': 'Minor Pentatonic',
        '12': 'Major Pentatonic',
        '13': 'Harmonic Minor',
        '14': 'Melodic Minor',
        '15': 'Super Locrian',
        '16': 'Bhairav',
        '17': 'Hungarian Minor',
        '18': 'Minor Gypsy',
        '19': 'Hirojoshi',
        '20': 'In-Sen',
        '21': 'Iwato',
        '22': 'Kumoi',
        '23': 'Pelog',
        '24': 'Spanish',
    }
    
    # Try to find the actual scale value
    if scale_info is not None:
        root_elem = None
        name_elem = None
        for child in scale_info:
            if child.tag == 'Root':
                root_elem = child
            elif child.tag == 'Name':
                name_elem = child
        
        if root_elem is not None:
            root_value = root_elem.get('Value', '0')
            print(f"Root note value: {root_value}")
            key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            try:
                root_idx = int(root_value)
                if 0 <= root_idx < 12:
                    print(f"Root note: {key_names[root_idx]}")
            except:
                pass
        
        if name_elem is not None:
            name_value = name_elem.get('Value', '0')
            print(f"Scale name value: {name_value}")
            if name_value in scale_name_map:
                print(f"Scale type: {scale_name_map[name_value]}")
            else:
                print(f"Unknown scale ID: {name_value}")

if __name__ == "__main__":
    als_file = Path("example-projects/McKenna-Bodhisattva Project/McKenna-Bodhisattva.als")
    if als_file.exists():
        examine_liveset_scale(als_file)
    else:
        print(f"File not found: {als_file}")
