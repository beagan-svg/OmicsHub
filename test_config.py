import yaml
import os

def test_pipeline_config():
    # Load the configuration
    with open('config/pipeline_config.yaml') as f:
        config = yaml.safe_load(f)
    
    # Test references
    print("\nTesting References:")
    print(f"Number of references: {len(config['references'])}")
    print(f"Sample references: {list(config['references'].keys())[:3]}")
    
    # Test chemistries
    print("\nTesting Chemistries:")
    print(f"Chemistry mappings: {config['chemistries']}")
    
    # Test workflows
    print("\nTesting Workflows:")
    print(f"Available workflows: {list(config['workflows'].keys())}")
    
    # Test MTX workflow
    mtx_config = config['workflows']['mtx']
    print("\nTesting MTX Workflow:")
    print(f"Alignment asset: {mtx_config['alignment']['asset_name']}")
    print(f"PostQC asset: {mtx_config['postqc']['asset_name']}")
    
    # Test RTX workflow
    rtx_config = config['workflows']['rtx']
    print("\nTesting RTX Workflow:")
    print(f"Alignment patterns: {list(rtx_config['alignment'].keys())}")
    print(f"PostQC patterns: {list(rtx_config['postqc'].keys())}")
    
    # Test settings
    print("\nTesting Settings:")
    print(f"Notification email: {config['settings']['notifications']['email']['recipients'][0]}")
    print(f"Check interval: {config['settings']['alignment']['check_interval_minutes']} minutes")

if __name__ == "__main__":
    test_pipeline_config() 