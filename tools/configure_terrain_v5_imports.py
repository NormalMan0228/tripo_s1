from pathlib import Path
root=Path(__file__).resolve().parents[1]/'labs/terrain_lab/assets'
data={'shore_distance','current_field','coast_field','headland_normals'}
for folder in ['v3','v5']:
    for path in (root/folder).glob('*.png.import'):
        text=path.read_text(encoding='utf-8')
        name=path.name.removesuffix('.png.import')
        if name in data:
            text=text.replace('process/fix_alpha_border=true','process/fix_alpha_border=false')
            text=text.replace('detect_3d/compress_to=1','detect_3d/compress_to=0')
        else:
            text=text.replace('mipmaps/generate=false','mipmaps/generate=true')
        path.write_text(text,encoding='utf-8')
print('V5_IMPORT_SETTINGS_READY')
