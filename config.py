from dotenv import load_dotenv
import os

load_dotenv()

# Blockchain Configuration
NETWORK = {
    'ethereum': {
        'name': 'Ethereum Mainnet',
        'chain_id': 1,
        'router': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',  # Uniswap V2 Router
        'weth': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',    # WETH
        'usdc': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',    # USDC
        'usdt': '0xdAC17F958D2ee523a2206206994597C13D831ec7',    # USDT
        'dai': '0x6B175474E89094C44Da98b954EedeAC495271d0F'      # DAI
    }
}

# Project Paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

# Create necessary directories
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Hybrid Trading Configuration
TRADING_CONFIG = {
    'max_investment_per_trade': 10,  # Maximum $10 investment
    'min_profit_usd': 1,  # Minimum profit target
    'max_loss_usd': 1,  # Maximum loss limit
    'max_slippage': 2,  # Maximum slippage percentage
    'gas_limit': 300000,  # Default gas limit
    'max_gas_price': 10 * 10**9,  # 10 Gwei max gas price
    'tx_timeout': 300,  # 5 minutes transaction timeout
    'position_sizing': {
        'base_size': 10,  # Base position size in USD
        'safety_multipliers': {
            90: 1.0,  # 100% of base size for safety score >= 90
            80: 0.8,  # 80% of base size for safety score >= 80
            70: 0.6,  # 60% of base size for safety score >= 70
            0: 0.4,   # 40% of base size for safety score < 70
        }
    },
    'profit_targets': {
        'min_take_profit': 15,  # Minimum take profit percentage
        'scaling_targets': {
            90: 30,  # 30% target for high potential trades
            80: 25,  # 25% target for good potential trades
            70: 20,  # 20% target for average potential trades
            0: 15,   # 15% target for lower potential trades
        }
    },
    'entry_rules': {
        'min_volume_score': 70,
        'min_safety_score': 80,
        'min_entry_quality': 60,
        'min_weighted_score': 75,
    },
    'exit_rules': {
        'trailing_stop': True,
        'trailing_distance': 5,  # 5% trailing stop
        'profit_lock': {
            10: 25,  # Lock in 25% of profits at 10% gain
            20: 50,  # Lock in 50% of profits at 20% gain
            30: 75,  # Lock in 75% of profits at 30% gain
        }
    },
    'analysis_weights': {
        'price_metrics': 1.5,
        'volume_metrics': 1.2,
        'liquidity_metrics': 1.3,
        'holder_metrics': 1.0,
        'contract_metrics': 1.4
    },
    'manipulation': {
        'sandwich_threshold': 0.8,
        'wash_trade_threshold': 0.7,
        'flash_loan_threshold': 0.9,
        'max_score': 0.6,
        'weights': {
            'price': 1.5,
            'volume': 1.2,
            'liquidity': 1.3,
            'trading': 1.0,
            'contract': 1.4
        },
        'warning_thresholds': {
            'price_manipulation': 0.7,
            'volume_manipulation': 0.7,
            'liquidity_manipulation': 0.8,
            'trading_manipulation': 0.7,
            'contract_manipulation': 0.8
        }
    }
}

# Volume Analysis Configuration
VOLUME_CONFIG = {
    'check_interval': 0.5,  # Check every 500ms
    'volume_patterns': {
        'breakout': {
            'min_increase': 200,  # Minimum % increase for breakout
            'confirmation_periods': 3,  # Number of periods to confirm
        },
        'accumulation': {
            'min_periods': 10,  # Minimum periods of steady buying
            'max_variance': 20,  # Maximum variance between periods
        },
        'distribution': {
            'min_periods': 5,  # Minimum periods of selling
            'volume_increase': 50,  # Minimum % volume increase
        }
    },
    'buy_pressure': {
        'min_ratio': 1.5,  # Minimum buy/sell ratio
        'sustained_periods': 5,  # Number of periods to sustain
    },
    'volume_quality': {
        'min_trade_size': 100,  # Minimum trade size in USD
        'max_single_trade': 1000,  # Maximum single trade in USD
        'healthy_distribution': 70,  # Minimum % of trades within range
    }
}

# Safety Metrics Configuration
SAFETY_CONFIG = {
    'contract': {
        'required_verification': True,
        'min_age_hours': 1,
        'banned_functions': [
            'blacklist', 'ban', 'freeze', 'mint',
            'pause', 'unpause', 'renounceOwnership'
        ],
        'required_functions': [
            'transfer', 'approve', 'transferFrom', 'balanceOf'
        ]
    },
    'liquidity': {
        'min_initial_usd': 10000,
        'min_locked_percentage': 80,
        'min_lock_time_days': 30,
        'max_single_wallet': 10,  # Maximum % owned by single wallet
    },
    'holders': {
        'min_count': 200,
        'max_top_holder': 15,  # Maximum % held by top wallet
        'max_team_wallets': 20,  # Maximum % held by team
    },
    'trading': {
        'max_buy_tax': 5,
        'max_sell_tax': 5,
        'max_price_impact': 3,
        'min_daily_trades': 50,
    }
}

# Profit Optimization Configuration
PROFIT_CONFIG = {
    'entry_optimization': {
        'dip_buy': {
            'min_dip': 5,  # Minimum % dip to consider
            'max_dip': 20,  # Maximum % dip to consider
            'volume_confirmation': True,
        },
        'breakout_confirmation': {
            'min_breakout': 10,  # Minimum % breakout
            'volume_multiplier': 2,  # Required volume increase
        },
    },
    'position_management': {
        'scaling': {
            'profit_scale_out': True,
            'scale_out_levels': [10, 20, 30],  # % profit levels
            'scale_out_portions': [25, 50, 75],  # % to scale out
        },
        'loss_management': {
            'max_loss_per_trade': 1,  # Maximum $1 loss
            'partial_exit': True,
            'partial_exit_threshold': 5,  # Exit 50% at 5% loss
        }
    }
}

# Event Monitor Configuration
EVENT_CONFIG = {
    'poll_interval': 1,  # Poll interval in seconds
    'data_retention_days': 7,
    'contract_abi_path': os.path.join(PROJECT_ROOT, 'data', 'contract_abis'),
    'event_types': {
        'trade': True,
        'liquidity': True,
        'transfer': True,
        'approval': True
    }
}

# Data Manager Configuration
DATA_CONFIG = {
    'storage_path': os.path.join(PROJECT_ROOT, 'data'),
    'retention_days': 30,
    'cache_size': 1000,
    'compression': True,
    'backup_enabled': True
}

# Network Manager Configuration
NETWORK_CONFIG = {
    'default_rpc': NETWORK['ethereum']['name'],
    'gas_oracle_url': 'https://api.etherscan.io/api',
    'networks': {
        'ethereum': {
            'rpc_url': NETWORK['ethereum']['name'],
            'chain_id': NETWORK['ethereum']['chain_id'],
            'explorer_url': 'https://etherscan.io',
            'gas_oracle': True
        }
    },
    'gas_settings': {
        'max_priority_fee': 2 * 10**9,  # 2 Gwei
        'max_fee': 10 * 10**9,  # 10 Gwei
        'min_priority_fee': 1 * 10**9  # 1 Gwei
    }
}

# Liquidity Manager Configuration
LIQUIDITY_CONFIG = {
    'pool_abi_path': os.path.join(PROJECT_ROOT, 'data', 'pool_abis'),
    'min_liquidity': 10000,  # Minimum liquidity in USD
    'max_price_impact': 3,  # Maximum price impact percentage
    'position_limits': {
        'min_position': 100,  # Minimum position size in USD
        'max_position': 10000,  # Maximum position size in USD
        'max_pool_share': 5  # Maximum percentage of pool ownership
    },
    'alerts': {
        'il_threshold': 5,  # Impermanent loss alert threshold
        'pool_health': 80,  # Minimum pool health score
        'price_deviation': 10  # Price deviation alert threshold
    }
}

# API Keys and Secrets
API_KEYS = {
    'dextools_api_key': os.getenv('DEXTOOLS_API_KEY'),
    'etherscan_api_key': os.getenv('ETHERSCAN_API_KEY'),
}
