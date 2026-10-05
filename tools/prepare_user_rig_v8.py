from pathlib import Path
R=Path(__file__).resolve().parents[1];p=R/'tools/blender_rig_user_head_v8.py';s=p.read_text().replace("A/'assembled_workbench.blend'","A/'lids_repaired_workbench.blend'");a=s.index('bound=json.loads');b=s.index('# Fit hair',a);s=s[:a]+s[b:];s=s.replace(" d=k.driver_add('value').driver;"," k.driver_remove('value');d=k.driver_add('value').driver;")
s=s.replace("  elif k.name.startswith('Blink_arc_'):","  elif k.name in {'Blink_L','Blink_R'}:drive(k,'blink.'+k.name[-1],'blink')\n  elif k.name.startswith('Blink_arc_'):")
p.write_text(s)
