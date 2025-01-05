# DEX Trading Bot

A decentralized exchange (DEX) trading bot with a web-based interface for monitoring and controlling trades on the Ethereum network.

## Features

- Real-time monitoring of wallet balances and gas prices
- Web-based interface for controlling the bot
- Support for Uniswap V2 trading pairs
- Configurable trading parameters and alerts
- Live transaction monitoring and logging
- Secure private key management

## Prerequisites

- Python 3.8 or later
- Git
- Web3 provider (Infura or Alchemy account)
- MetaMask or other Ethereum wallet

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/dex-trading-bot.git
cd dex-trading-bot
```

2. Create and configure your environment file:
```bash
copy .env.example .env
```

Edit `.env` with your settings:
```
ETHEREUM_RPC_URL=your_infura_or_alchemy_url
PRIVATE_KEY=your_wallet_private_key
MAX_SLIPPAGE=2
GAS_LIMIT=300000
MAX_GAS_PRICE=150
```

3. Run the bot:
```bash
start_bot.bat
```

The web interface will open automatically at `http://127.0.0.1:8081`

## Project Structure

```
dex_trading_bot/
├── abi/                    # Contract ABIs
│   ├── router.json        # Uniswap V2 Router ABI
│   └── erc20.json         # ERC20 Token ABI
├── data/                   # Trading data storage
├── logs/                   # Log files
├── static/                 # Web interface static files
│   └── js/
│       └── main.js        # Frontend JavaScript
├── templates/             # HTML templates
│   └── index.html        # Main web interface
├── .env                  # Environment configuration
├── .env.example         # Example environment file
├── config.py           # Bot configuration
├── trader.py          # Trading logic
├── web_server.py     # Web interface server
├── requirements.txt  # Python dependencies
├── start_bot.bat    # Windows startup script
└── README.md       # This file
```

## Configuration

### Environment Variables

- `ETHEREUM_RPC_URL`: Your Ethereum node RPC URL (Infura/Alchemy)
- `PRIVATE_KEY`: Your wallet's private key
- `MAX_SLIPPAGE`: Maximum allowed slippage percentage (default: 2)
- `GAS_LIMIT`: Maximum gas limit for transactions (default: 300000)
- `MAX_GAS_PRICE`: Maximum gas price in Gwei (default: 150)

### Trading Settings

Configure trading parameters in the web interface:
- Slippage tolerance
- Gas price limits
- Price monitoring intervals
- Alert settings

## Security

- Never share your private key
- Keep your `.env` file secure
- Use a dedicated trading wallet
- Monitor transactions regularly
- Set reasonable gas and slippage limits

## Troubleshooting

### Common Issues

1. **Connection Error**
   - Check your RPC URL in `.env`
   - Verify internet connection
   - Ensure RPC provider is operational

2. **Transaction Failures**
   - Check gas price settings
   - Verify wallet has sufficient ETH
   - Check token approvals

3. **Web Interface Issues**
   - Check logs in `logs/bot.log`
   - Verify port 8081 is available
   - Restart the bot

### Logs

- Check `logs/bot.log` for runtime logs
- Check `logs/startup.log` for initialization logs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

Trading cryptocurrencies carries significant risk. This bot is for educational purposes only. Always test thoroughly with small amounts first.
