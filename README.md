# DEX Trading Bot

A decentralized exchange (DEX) trading bot with a web-based interface for monitoring and controlling trades on the Ethereum network.

## Step-by-Step Setup Guide

### 1. Clone the Repository
```bash
git clone https://github.com/ConejoFastDL/dex-trading-bot.git
cd dex-trading-bot
```

### 2. Set Up Python Environment
Make sure you have Python 3.8 or later installed:
```bash
python --version  # Should show 3.8 or higher
```

### 3. Configure Environment Variables
1. Copy the example environment file:
   ```bash
   copy .env.example .env
   ```

2. Edit `.env` file with your details:
   - Get an RPC URL:
     1. Go to [Infura](https://infura.io/) or [Alchemy](https://www.alchemy.com/)
     2. Create a free account
     3. Create a new project
     4. Copy your Ethereum Mainnet RPC URL
     5. Paste it as your `ETHEREUM_RPC_URL`

   - Set up your wallet:
     1. Get your wallet's private key (from MetaMask or other wallet)
     2. NEVER share this key with anyone
     3. Paste it as your `PRIVATE_KEY` (without 0x prefix)

### 4. Install Dependencies
The bot will automatically create a virtual environment and install dependencies when you run it.

### 5. Start the Bot
1. Double-click `start_bot.bat`
   - This will:
     - Create a virtual environment
     - Install required packages
     - Start the web server
     - Open the web interface

2. Alternative manual start:
   ```bash
   # Create and activate virtual environment
   python -m venv venv
   .\venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt

   # Start the bot
   python web_server.py
   ```

### 6. Access the Web Interface
- Open your browser to: http://127.0.0.1:8081
- The interface should show:
  - Your wallet balance
  - Current gas prices
  - Trading pairs
  - Settings modal

## Troubleshooting

### Common Issues

1. **"Python is not recognized..."**
   - Make sure Python is installed
   - Add Python to your system PATH
   - Try using `python3` instead of `python`

2. **"No module named..."**
   - Delete the `venv` folder
   - Run `start_bot.bat` again to recreate it
   - Or manually: `pip install -r requirements.txt`

3. **"Could not connect to RPC..."**
   - Check your `ETHEREUM_RPC_URL` in `.env`
   - Make sure you have internet connection
   - Verify your Infura/Alchemy project is active

4. **"Invalid private key..."**
   - Make sure your private key is correct
   - Remove any `0x` prefix
   - Check for extra spaces or characters

5. **"Port 8081 already in use"**
   - Close other applications using port 8081
   - Or modify `web_server.py` to use a different port

### Checking Logs
- Check `logs/startup.log` for initialization errors
- Check `logs/bot.log` for runtime errors
- Check `logs/pip_install.log` for dependency issues

## Security Notes

⚠️ IMPORTANT:
- Never share your private key
- Use a dedicated trading wallet
- Start with small amounts
- Monitor transactions regularly
- Keep your `.env` file secure

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
