"""
Configuration Loader
====================
Loads and validates frozen v1.0 parameters.
Enforces modification lock.
"""

import yaml
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


class ConfigLoader:
    """Loads and validates configuration files."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.params: Dict[str, Any] = {}
        self.instruments: Dict[str, Any] = {}
        
    def load_all(self) -> None:
        """Load all configuration files."""
        self.params = self._load_yaml("v1_params.yaml")
        self.instruments = self._load_yaml("instrument_specs.yaml")
        self._validate_frozen_status()
        
    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """Load a YAML configuration file."""
        filepath = self.config_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"Config file not found: {filepath}")
            
        with open(filepath, 'r') as f:
            config = yaml.safe_load(f)
            
        return config
    
    def _validate_frozen_status(self) -> None:
        """Validate that v1.0 is still frozen."""
        if not self.params.get('modification_lock', False):
            raise ValueError(
                "Configuration modification_lock is disabled! "
                "v1.0 parameters must remain frozen until 50 trades completed."
            )
        
        # Check version
        version = self.params.get('version', 'unknown')
        if version != "1.0":
            raise ValueError(f"Expected v1.0, got version {version}")
        
        # Log frozen status
        frozen_date = self.params.get('frozen_date', 'unknown')
        print(f"✅ v1.0 Configuration Loaded (Frozen: {frozen_date})")
        print("⚠️  Modification Lock: ACTIVE")
        print("📋 Changes prohibited until 50 live trades completed\n")
    
    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Example:
            config.get('session', 'timezone')
            config.get('risk', 'tp1_r')
        """
        value = self.params
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
            else:
                return default
        return value
    
    def get_instrument_spec(self, symbol: str) -> Dict[str, Any]:
        """Get instrument specifications."""
        if symbol not in self.instruments:
            raise ValueError(f"Instrument {symbol} not found in specs")
        return self.instruments[symbol]


class Config:
    """Global configuration singleton."""
    _instance: ConfigLoader = None
    
    @classmethod
    def initialize(cls, config_dir: str = "config") -> None:
        """Initialize the global configuration."""
        if cls._instance is None:
            cls._instance = ConfigLoader(config_dir)
            cls._instance.load_all()
    
    @classmethod
    def get(cls, *keys: str, default: Any = None) -> Any:
        """Get configuration value."""
        if cls._instance is None:
            raise RuntimeError("Config not initialized. Call Config.initialize() first.")
        return cls._instance.get(*keys, default=default)
    
    @classmethod
    def get_instrument_spec(cls, symbol: str) -> Dict[str, Any]:
        """Get instrument specification."""
        if cls._instance is None:
            raise RuntimeError("Config not initialized. Call Config.initialize() first.")
        return cls._instance.get_instrument_spec(symbol)


# Example usage:
if __name__ == "__main__":
    # Initialize config
    Config.initialize()
    
    # Access parameters
    print("Timezone:", Config.get('session', 'timezone'))
    print("Max trades per session:", Config.get('session', 'max_trades_per_session'))
    print("TP1 R-multiple:", Config.get('risk', 'tp1_r'))
    
    # Get instrument specs
    nq_spec = Config.get_instrument_spec('NQ')
    print(f"\nNQ Tick Size: {nq_spec['tick_size']}")
    print(f"NQ Tick Value: ${nq_spec['tick_value']}")
