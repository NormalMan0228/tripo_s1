"""Normalize an operator-reviewed Scenario export into self-contained GLB.

For authored game assets only; player-generated objects use the strict server validator.
Converts embedded data-URI images to binary buffer views and corrects MIME from magic.
"""
import argparse
import base64
import json
from pathlib import Path
import struct

def normalize(blob):
    if len(blob)>30*1024*1024 or len(blob)<28:
        raise ValueError('invalid_glb_size')
    magic,version,size=struct.unpack_from('<III',blob)
    if (magic,version,size)!=(0x46546c67,2,len(blob)):
        raise ValueError('invalid_glb_header')
    jsize,jkind=struct.unpack_from('<II',blob,12)
    if jkind!=0x4e4f534a: raise ValueError('missing_glb_json')
    doc=json.loads(blob[20:20+jsize])
    offset=20+jsize
    bsize,bkind=struct.unpack_from('<II',blob,offset)
    if bkind!=0x004e4942 or offset+8+bsize!=len(blob): raise ValueError('invalid_glb_binary')
    buffers=doc['buffers']
    if len(buffers)!=1 or 'uri' in buffers[0]: raise ValueError('external_buffer_rejected')
    binary=bytearray(blob[offset+8:offset+8+bsize])
    views=doc.setdefault('bufferViews',[])
    for image in doc.get('images',[]):
        if 'uri' not in image: continue
        uri=image.pop('uri')
        if not uri.startswith(('data:image/png;base64,','data:image/jpeg;base64,')):
            raise ValueError('external_image_rejected')
        data=base64.b64decode(uri.split(',',1)[1],validate=True)
        if data.startswith(b'\x89PNG\r\n\x1a\n'): mime='image/png'
        elif data.startswith(b'\xff\xd8\xff'): mime='image/jpeg'
        else: raise ValueError('unknown_image_format')
        binary.extend(b'\0'*((-len(binary))%4))
        image.update(bufferView=len(views),mimeType=mime)
        views.append({'buffer':0,'byteOffset':len(binary),'byteLength':len(data)})
        binary.extend(data)
    buffers[0]['byteLength']=len(binary)
    binary.extend(b'\0'*((-len(binary))%4))
    js=json.dumps(doc,separators=(',',':')).encode('utf-8')
    js+=b' '*((-len(js))%4)
    return struct.pack('<III',magic,2,28+len(js)+len(binary))+struct.pack('<II',len(js),jkind)+js+struct.pack('<II',len(binary),bkind)+binary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path); parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    args.destination.write_bytes(normalize(args.source.read_bytes()))
    print('Authored asset normalized successfully.')
