"""
Pipeline configuration utilities.
"""
import os
import yaml
import logging
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)

# Path to pipeline configuration file
PIPELINE_CONFIG_PATH = Path(os.path.join('config', 'pipeline_config.yaml'))

def load_pipeline_config():
    """Load pipeline configuration from yaml file"""
    if PIPELINE_CONFIG_PATH.exists():
        with open(PIPELINE_CONFIG_PATH, 'r') as f:
            try:
                return yaml.safe_load(f)
            except Exception as e:
                logger.error(f"Error loading pipeline config: {str(e)}")
                return {}
    else:
        # Return default configuration
        return {
            "references": {
                "armadillo": "armadillo_ncbi_mdasnov1-hap2_genome_star2-7-1a",
                "human": "human_10x_grch38_genome_star2.7.1a",
                "mouse": "mouse_10x_mm10_genome_star2.7.1a",
            },
            "chemistries": {
                "10xV3.1D": "SC3Pv3",
                "10xRseq_Mult_noATAC": "ARC-v1",
                "10xV3.1_HT": "SC3Pv3HT",
                "10xV4": "SC3Pv4",
                "10Xv2": "SC3Pv2"
            }
        }

def get_reference_name(organism_common_name):
    """Get reference name for an organism"""
    config = load_pipeline_config()
    references = config.get('references', {})
    
    # Normalize organism name (lowercase, replace spaces with underscores)
    normalized_name = organism_common_name.lower().replace(' ', '_')
    
    # Try direct lookup first
    if normalized_name in references:
        return references[normalized_name]
    
    # Try partial matching
    for key in references:
        if key in normalized_name or normalized_name in key:
            return references[key]
    
    # Default to human if no match
    logger.warning(f"No reference found for organism: {organism_common_name}, using human as default")
    return references.get('human', 'human_10x_grch38_genome_star2.7.1a')

def get_chemistry(library_prep_method):
    """Get chemistry value for a library prep method"""
    config = load_pipeline_config()
    chemistries = config.get('chemistries', {})
    
    # Try direct lookup
    if library_prep_method in chemistries:
        return chemistries[library_prep_method]
    
    # Default to SC3Pv3 if no match
    logger.warning(f"No chemistry found for library prep: {library_prep_method}, using SC3Pv3 as default")
    return chemistries.get('10xV3.1D', 'SC3Pv3') 