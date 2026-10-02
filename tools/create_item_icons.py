"""Create original vector inventory art, without external images or generation services."""
from pathlib import Path

icons={
'wood': '''<path d="M15 39 39 14 53 27 29 52Z" fill="#a9794c"/><path d="m15 39 14 13 4-13-14-12Z" fill="#d8b47b"/><ellipse cx="24" cy="42" rx="7" ry="9" transform="rotate(-40 24 42)" fill="#efce91"/><ellipse cx="24" cy="42" rx="3" ry="5" transform="rotate(-40 24 42)" fill="none"/><path d="m32 25 11 10m-6-16 11 10" fill="none"/>''',
'stone': '''<path d="m10 44 5-24 20-11 17 16 3 22-26 9Z" fill="#b7c5c2"/><path d="m15 20 19 11 18-6-17-16Z" fill="#dbe0d5"/><path d="m34 31-5 25 26-9-3-22Z" fill="#718f94"/><path d="m10 44 24-13-19-11Z" fill="#a0b5b3"/>''',
'berry': '''<path d="m30 31 7-20m-2 11 12-7" fill="none" stroke="#95b970" stroke-width="4"/><path d="M34 20Q19 7 15 19q10 9 19 1" fill="#7aa56f"/><circle cx="22" cy="36" r="12" fill="#d97377"/><circle cx="42" cy="35" r="11" fill="#e59887"/><circle cx="33" cy="47" r="11" fill="#ba596b"/><path d="m17 31 4-2m17 1 3-1m-12 15 3-2" stroke="#f6ceb7" fill="none" stroke-width="3"/>''',
'fiber': '''<path d="M29 52Q8 35 12 12q15 12 17 40" fill="#88a768"/><path d="M33 54Q29 17 40 8q5 24-7 46" fill="#c3cf83"/><path d="M34 51Q41 24 55 19q0 21-21 32" fill="#a1b779"/><path d="m26 38 14 5m-15 1 13 6" stroke="#dfb077" stroke-width="5"/>''',
'axe': '''<path d="m15 53 25-35 5 3-25 36Z" fill="#b98b59"/><path d="m34 15 12-6 13 9-5 17-15-6-7-7Z" fill="#b4c4c0"/><path d="m46 9 13 9-5 17-4-13Z" fill="#e1e2ce"/><path d="m31 22 11 7m-13-3 11 7" stroke="#dfb978" stroke-width="4" fill="none"/>''',
'spear': '''<path d="m13 53 29-32 4 4-29 32Z" fill="#b68b5c"/><path d="m34 22 23-16-6 26-13-5Z" fill="#d8e0d3"/><path d="M57 6 38 27l13 5Z" fill="#8eaaa9"/><path d="m30 29 8 7m-5-10 8 7" stroke="#dfba85" stroke-width="3" fill="none"/>''',
'soup': '''<path d="M10 33h44q-1 20-22 23Q12 53 10 33" fill="#c08c60"/><ellipse cx="32" cy="33" rx="22" ry="8" fill="#ecbb77"/><path d="M25 24q-7-6 0-12m12 12q-7-6 0-12" fill="none" stroke="#e9dfbd" stroke-width="3"/><circle cx="25" cy="32" r="3" fill="#c86865"/><circle cx="38" cy="34" r="3" fill="#8baa72"/>''',
'bandage': '''<path d="m10 36 26-25 20 19-25 25Z" fill="#e3d7b9"/><path d="m24 23 18 19m-25-12 18 19m-17-1 25-25" stroke="#bdb193" fill="none"/><path d="m29 26 9 9-9 9-9-9Z" fill="#d48c7a"/><path d="m24 34 10 1m-5-5 1 10" stroke="#f4e7cd" fill="none" stroke-width="3"/>'''
}

root=Path(__file__).resolve().parents[1]/'game/assets/items'
root.mkdir(exist_ok=True)
for name,body in icons.items():
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><g stroke="#405653" stroke-width="2" stroke-linejoin="round" stroke-linecap="round">{body}</g></svg>'
    (root/f'{name}.svg').write_text(svg,encoding='utf-8')
print(f'Created {len(icons)} original item icons')
