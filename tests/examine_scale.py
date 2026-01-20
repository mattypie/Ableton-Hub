"""Examine scale/key information in Ableton .als files."""

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path

def examine_scale_info(als_path: Path):
    """Examine scale/key information in an .als file."""
    print(f"Examining: {als_path}")
    print("=" * 80)
    
    with gzip.open(als_path, 'rb') as f:
        xml_data = f.read()
    
    root = ET.fromstring(xml_data)
    
    # Look for ScaleInformation elements
    print("\n=== ScaleInformation Elements ===")
    scale_info_count = 0
    for elem in root.iter():
        if 'ScaleInformation' in elem.tag:
            scale_info_count += 1
            print(f"\nScaleInformation #{scale_info_count}:")
            print(f"  Tag: {elem.tag}")
            print(f"  Attributes: {elem.attrib}")
            
            # Look for child elements
            for child in elem:
                print(f"  Child: {child.tag}, Attr: {child.attrib}")
                for subchild in child:
                    if subchild.text or subchild.attrib:
                        print(f"    Subchild: {subchild.tag}, Attr: {subchild.attrib}, Text: {subchild.text}")
    
    # Look for RootNote elements
    print("\n=== RootNote Elements ===")
    root_note_count = 0
    for elem in root.iter():
        if 'RootNote' in elem.tag or 'RootNote' in str(elem.attrib):
            root_note_count += 1
            print(f"\nRootNote #{root_note_count}:")
            print(f"  Tag: {elem.tag}")
            print(f"  Attributes: {elem.attrib}")
            if elem.text:
                print(f"  Text: {elem.text[:200]}")
    
    # Look for MidiKey elements
    print("\n=== MidiKey Elements ===")
    midi_key_count = 0
    for elem in root.iter():
        if 'MidiKey' in elem.tag:
            midi_key_count += 1
            if midi_key_count <= 5:  # Show first 5
                print(f"\nMidiKey #{midi_key_count}:")
                print(f"  Tag: {elem.tag}")
                print(f"  Attributes: {elem.attrib}")
                # Get parent context
                parent = elem.getparent() if hasattr(elem, 'getparent') else None
                if parent is not None:
                    print(f"  Parent: {parent.tag}, Attr: {parent.attrib}")
    print(f"\nTotal MidiKey elements found: {midi_key_count}")
    
    # Look for IsInKey elements
    print("\n=== IsInKey Elements ===")
    is_in_key_count = 0
    for elem in root.iter():
        if 'IsInKey' in elem.tag:
            is_in_key_count += 1
            if is_in_key_count <= 5:  # Show first 5
                print(f"\nIsInKey #{is_in_key_count}:")
                print(f"  Tag: {elem.tag}")
                print(f"  Attributes: {elem.attrib}")
                # Get parent context
                parent = elem.getparent() if hasattr(elem, 'getparent') else None
                if parent is not None:
                    print(f"  Parent: {parent.tag}, Attr: {parent.attrib}")
    print(f"\nTotal IsInKey elements found: {is_in_key_count}")
    
    # Look for KeyTrack elements
    print("\n=== KeyTrack Elements ===")
    key_track_count = 0
    for elem in root.iter():
        if 'KeyTrack' in elem.tag:
            key_track_count += 1
            if key_track_count <= 3:  # Show first 3
                print(f"\nKeyTrack #{key_track_count}:")
                print(f"  Tag: {elem.tag}")
                print(f"  Attributes: {elem.attrib}")
                # Show children
                for child in elem:
                    print(f"  Child: {child.tag}, Attr: {child.attrib}")
    print(f"\nTotal KeyTrack elements found: {key_track_count}")
    
    # Look for global/project-level scale settings
    print("\n=== Looking for Global Scale Settings ===")
    # Check root level and common parent elements
    for elem_name in ['LiveSet', 'MasterTrack', 'Tracks', 'SongMasterTrack']:
        for elem in root.iter():
            if elem_name in elem.tag:
                print(f"\n{elem_name} element found:")
                print(f"  Tag: {elem.tag}")
                print(f"  Attributes: {elem.attrib}")
                # Check for scale-related children
                scale_children = [c for c in elem if 'Scale' in c.tag or 'Key' in c.tag or 'RootNote' in c.tag]
                if scale_children:
                    print(f"  Scale-related children found: {len(scale_children)}")
                    for child in scale_children[:3]:
                        print(f"    {child.tag}: {child.attrib}")

if __name__ == "__main__":
    als_file = Path("example-projects/McKenna-Bodhisattva Project/McKenna-Bodhisattva.als")
    if als_file.exists():
        examine_scale_info(als_file)
    else:
        print(f"File not found: {als_file}")
