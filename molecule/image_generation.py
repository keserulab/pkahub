"""
On-the-fly image generation utilities for microspecies visualization.

This module provides utilities for generating molecule images dynamically,
useful for displaying calculated molecules not stored in the database.
"""

from django.http import HttpResponse
from django.core.cache import cache
import hashlib

try:
    from rdkit import Chem
    from rdkit.Chem import Draw
    from io import BytesIO
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False


def generate_microspecies_image(request):
    """
    Generate a molecule image from SMILES on the fly.

    GET parameters:
        smiles: SMILES string of the molecule
        size: Optional image size (default: 250)

    Returns:
        PNG image as HttpResponse

    Example:
        /molecule/generate-image/?smiles=CCO&size=300
    """
    if not RDKIT_AVAILABLE:
        return HttpResponse("RDKit not available", status=500)

    smiles = request.GET.get('smiles', '')
    size = int(request.GET.get('size', '250'))

    if not smiles:
        return HttpResponse("Missing SMILES parameter", status=400)

    # Create cache key
    cache_key = f"molimg_{hashlib.md5(f'{smiles}_{size}'.encode()).hexdigest()}"

    # Check cache
    cached_image = cache.get(cache_key)
    if cached_image:
        return HttpResponse(cached_image, content_type='image/png')

    try:
        # Generate molecule image
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return HttpResponse("Invalid SMILES", status=400)

        # Generate PNG image
        img = Draw.MolToImage(mol, size=(size, size))

        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        image_bytes = buffer.getvalue()

        # Cache for 1 hour
        cache.set(cache_key, image_bytes, 3600)

        return HttpResponse(image_bytes, content_type='image/png')

    except Exception as e:
        return HttpResponse(f"Error generating image: {str(e)}", status=500)


def generate_microspecies_svg(request):
    """
    Generate a molecule SVG from SMILES on the fly.

    GET parameters:
        smiles: SMILES string of the molecule
        width: Optional SVG width (default: 250)
        height: Optional SVG height (default: 250)

    Returns:
        SVG image as HttpResponse

    Example:
        /molecule/generate-svg/?smiles=CCO&width=300&height=300
    """
    if not RDKIT_AVAILABLE:
        return HttpResponse("RDKit not available", status=500)

    smiles = request.GET.get('smiles', '')
    width = int(request.GET.get('width', '250'))
    height = int(request.GET.get('height', '250'))

    if not smiles:
        return HttpResponse("Missing SMILES parameter", status=400)

    # Create cache key
    cache_key = f"molsvg_{hashlib.md5(f'{smiles}_{width}_{height}'.encode()).hexdigest()}"

    # Check cache
    cached_svg = cache.get(cache_key)
    if cached_svg:
        return HttpResponse(cached_svg, content_type='image/svg+xml')

    try:
        # Generate molecule SVG
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return HttpResponse("Invalid SMILES", status=400)

        # Generate SVG
        drawer = Draw.MolDraw2DSVG(width, height)
        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()
        svg = drawer.GetDrawingText()

        # Cache for 1 hour
        cache.set(cache_key, svg, 3600)

        return HttpResponse(svg, content_type='image/svg+xml')

    except Exception as e:
        return HttpResponse(f"Error generating SVG: {str(e)}", status=500)
