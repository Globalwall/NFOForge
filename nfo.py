from pathlib import Path
import xml.etree.ElementTree as ET


def write_nfo(video_path: Path, provider: str, provider_id: str, title: str) -> Path:
    movie = ET.Element("movie")
    ET.SubElement(movie, "title").text = title
    unique_id = ET.SubElement(movie, "uniqueid", {"type": provider, "default": "true"})
    unique_id.text = str(provider_id)

    nfo_path = video_path.with_suffix(".nfo")
    tree = ET.ElementTree(movie)
    ET.indent(tree, space="  ")
    tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
    return nfo_path
