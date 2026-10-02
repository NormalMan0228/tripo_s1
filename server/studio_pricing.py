"""Provider estimates, distinct from the game's reward currency and actual billing."""
from .provider import ProviderError

def mesh_credits(model,textured,image=False):
    if model=='P2-20260801':return 110 if textured else 100
    if model=='v3.1-20260211':return 10+10*bool(image)+10*bool(textured)
    raise ProviderError('provider_price_not_configured')

def estimate(model,textured,part_count,reference=False,refine=False):
    image=reference and (part_count==1 or refine)
    return part_count*(mesh_credits(model,textured,image)+(5 if refine else 0))
