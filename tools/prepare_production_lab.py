from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'labs/character_lab';dest=ROOT/'labs/production_lab'
if (dest/'lab.gd').exists():
 raise SystemExit('Production Lab already exists; preserve its reviewed controller and tests.')
(dest/'project.godot').write_text((src/'project.godot').read_text(encoding='utf-8').replace('Character Atelier','Production Motion Lab'),encoding='utf-8')
(dest/'lab.tscn').write_text((src/'lab.tscn').read_text(encoding='utf-8'),encoding='utf-8')
t=(src/'lab.gd').read_text(encoding='utf-8');t=t[:t.index('func run_acceptance()')]
t=t.replace('V5','Production Lab').replace('신규 몸체 + 보강한 기존 손 · Blender 전용 동작','Tripo 단일 몸체 · 루트 정규화 · 속도/위상 동기화')
t=t.replace('[["대기","idle"],["걷기","walk"],["달리기","run"],["손 동작","hands"],["팔 뻗기","reach"]]','[["대기","idle"],["걷기","walk"],["달리기","run"]]')
t=t.replace('set_motion("hands")','set_motion("idle")')
t=t.replace('actor.animator.active=true;playback=true','actor.paused=false;actor.animator.active=true;playback=true')
t=t.replace('actor.animator.active=playback','actor.paused=not playback;actor.animator.active=playback')
t=t.replace('if acceptance:call_deferred("run_acceptance")','if acceptance:call_deferred("run_acceptance")')
(dest/'lab.gd').write_text(t,encoding='utf-8')
ik=(src/'locomotion_pose.gd').read_text(encoding='utf-8')
ik=ik[:ik.index('func _process_modification_with_delta')]
ik+= '''func _process_modification_with_delta(delta: float) -> void:
	if not is_instance_valid(actor) or legs.size()!=2:return
	var skeleton := get_skeleton()
	contact_error=0
	for i in 2:
		var leg: Dictionary=legs[i]
		var strength: float=actor.contact_strength(i) if actor.mode=="play" and actor.is_on_floor() else 0.0
		var foot_world: Vector3=skeleton.global_transform*skeleton.get_bone_global_pose(leg.foot).origin
		if strength>.6 and not leg.contact:
			leg.target=foot_world
			var query := PhysicsRayQueryParameters3D.create(foot_world+Vector3.UP*.35,foot_world-Vector3.UP*.5)
			query.exclude=[actor.get_rid()]
			var hit: Dictionary=actor.get_world_3d().direct_space_state.intersect_ray(query)
			if not hit.is_empty():leg.target.y=hit.position.y+.045
			leg.contact=true
		if strength<.25:leg.contact=false
		var goal := strength if leg.contact else 0.0
		leg["weight"]=move_toward(float(leg.get("weight",0.0)),goal,delta*14)
		if leg.get("weight",0.0)>.001:
			var hip_world: Vector3=skeleton.global_transform*skeleton.get_bone_global_pose(leg.hip).origin
			if hip_world.distance_to(leg.target)>float(leg.reach)*.98:
				leg.contact=false;leg["weight"]=maxf(0,float(leg.weight)-delta*14)
			solve(skeleton,leg,leg.target,leg.weight)
'''
(dest/'foot_lock.gd').write_text(ik,encoding='utf-8')
print('PRODUCTION_LAB_PREPARED')
