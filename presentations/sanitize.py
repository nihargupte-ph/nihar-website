import re
import xml.etree.ElementTree as ET

SVG_NS = 'http://www.w3.org/2000/svg'
XLINK_NS = 'http://www.w3.org/1999/xlink'
_BAD_TAGS = {'script', 'foreignObject', 'iframe', 'object', 'embed'}
_HREF_KEYS = ('href', f'{{{XLINK_NS}}}href')
_XML_DECL = re.compile(r'<\?xml[^>]*\?>\s*')


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _safe_href(v):
    v = (v or '').strip()
    return v.startswith('#') or v.lower().startswith('data:')


def sanitize_svg(text):
    ET.register_namespace('', SVG_NS)
    ET.register_namespace('xlink', XLINK_NS)
    root = ET.fromstring(_XML_DECL.sub('', text))
    for parent in list(root.iter()):
        for child in list(parent):
            if _local(child.tag) in _BAD_TAGS:
                parent.remove(child)
    if _local(root.tag) in _BAD_TAGS:
        raise ValueError('root element not allowed')
    for el in root.iter():
        for k in list(el.attrib):
            if _local(k).lower().startswith('on'):
                del el.attrib[k]
            elif k in _HREF_KEYS and not _safe_href(el.attrib[k]):
                del el.attrib[k]
            elif _local(k) == 'style' and 'url(' in el.attrib[k] and 'url(#' not in el.attrib[k]:
                del el.attrib[k]
    return ET.tostring(root, encoding='unicode')
