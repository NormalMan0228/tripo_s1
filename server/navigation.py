"""Small bounded navigation grid for the survival forest. No client-supplied paths."""
from functools import lru_cache
import heapq
import math


def solids(state):
    resources=tuple((n['x'],n['z'],.9) for n in state['nodes'] if n['kind'] in ('tree','stone') and n['quantity']>0)
    return resources+tuple((o['x'],o['z'],o['radius']+.3) for o in state.get('obstacles',[]))


def segment_open(state,a,b,radius=.9,pit_radius=1.08):
    dx,dz=b[0]-a[0],b[1]-a[1]
    length_sq=max(.0001,dx*dx+dz*dz)
    obstacles=[(x,z,radius if r==.9 else r) for x,z,r in solids(state)]
    if pit_radius: obstacles.append((0.,0.,pit_radius))
    for x,z,r in obstacles:
        t=max(0.,min(1.,((x-a[0])*dx+(z-a[1])*dz)/length_sq))
        if math.hypot(x-a[0]-t*dx,z-a[1]-t*dz)<r: return False
    return True


@lru_cache(maxsize=128)
def blocked_cells(obstacles):
    blocked={(0,0),(1,0),(-1,0),(0,1),(0,-1)}
    for x,z,r in obstacles:
        extent=math.ceil(r)+1
        for gx in range(round(x)-extent,round(x)+extent+1):
            for gz in range(round(z)-extent,round(z)+extent+1):
                if math.hypot(gx-x,gz-z)<r+.15: blocked.add((gx,gz))
    return frozenset(blocked)


def path_to(state,start,goal):
    """At most 37x37 cells. Recomputed after depletion/regrowth or a moved target."""
    start=(max(-18,min(18,round(start[0]))),max(-18,min(18,round(start[1]))))
    goal=(max(-18,min(18,round(goal[0]))),max(-18,min(18,round(goal[1]))))
    blocked=blocked_cells(solids(state))-{start,goal}
    frontier=[(0.,start)]
    cost={start:0.}
    parent={}
    directions=[(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
    while frontier:
        _,current=heapq.heappop(frontier)
        if current==goal:
            route=[]
            while current!=start:
                route.append(list(current))
                current=parent[current]
            return route[::-1]
        for dx,dz in directions:
            nxt=(current[0]+dx,current[1]+dz)
            if max(abs(nxt[0]),abs(nxt[1]))>18 or nxt in blocked: continue
            if dx and dz and ((current[0]+dx,current[1]) in blocked or (current[0],current[1]+dz) in blocked): continue
            new_cost=cost[current]+(math.sqrt(2) if dx and dz else 1.)
            if new_cost>=cost.get(nxt,math.inf): continue
            cost[nxt]=new_cost
            parent[nxt]=current
            heapq.heappush(frontier,(new_cost+math.hypot(nxt[0]-goal[0],nxt[1]-goal[1]),nxt))
    return []
