from rdkit import Chem
from rdkit.Chem import Draw

def save_molecule_image(mol: Chem.Mol, filepath: str, size=(400, 300)) -> None:
    """
    Save a 2D image of the given molecule to the specified file path.
    
    Args:
        mol: RDKit molecule object
        filepath: Path to save the image file
        size: Tuple specifying the image size (width, height)
    """
    # Save to PNG
    #Draw.MolToFile(mol, "name.png", size=(400, 300))
    # Save to JPG
    #Draw.MolToFile(mol, "name.jpg", size=(400, 300))
    img = Draw.MolToImage(mol, size=size)
    img.save(filepath)