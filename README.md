# DEX Trading Bot with Web Interface

A decentralized exchange trading bot with a web-based user interface for monitoring and controlling trades on Ethereum mainnet.

## Features

- Real-time wallet balance monitoring
- Gas price tracking
- Trading pair management
- Live trading execution
- Web-based control interface
- Integration with MetaMask and Infura
- Support for Uniswap V2

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a .env file with your configuration:
   ```
   # Network Configuration
   ETHEREUM_RPC_URL=https://mainnet.infura.io/v3/YOUR-PROJECT-ID

   # Wallet Configuration
   PRIVATE_KEY=your_private_key_here
   WALLET_ADDRESS=your_wallet_address_here

   # Trading Configuration
   MAX_SLIPPAGE=2
   GAS_LIMIT=300000
   DEFAULT_NETWORK=ethereum

   # Monitoring Configuration
   PRICE_UPDATE_INTERVAL=60
   EVENT_POLLING_INTERVAL=30
   POSITION_CHECK_INTERVAL=300
   ```

4. Start the web interface:
   ```bash
   python web_server.py
   ```

5. Access the web interface at http://127.0.0.1:8081

## Directory Structure

- `trader.py` - Main trading logic
- `web_server.py` - Web interface server
- `config.py` - Configuration settings
- `static/` - Static web files
- `templates/` - HTML templates
- `data_manager.py` - Data management utilities
- `contract_analyzer.py` - Smart contract analysis tools

## Usage

1. Start the web server
2. Open http://127.0.0.1:8081 in your browser
3. Use the interface to:
   - Monitor wallet balance and gas prices
   - Add/remove trading pairs
   - Start/stop the trading bot
   - View trading history and performance

## Security

- Never share your private key
- Store sensitive information in .env file
- Use environment variables for API keys
- Keep your MetaMask secure

## Dependencies

- Web3.py for Ethereum interaction
- aiohttp for web server
- python-dotenv for environment variables
- eth-account for wallet management
