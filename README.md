#  Peer-to-Peer Blockchain Network with Flask

A lightweight distributed blockchain implementation using Python and Flask. This system supports mining, transactions, peer-to-peer synchronization, and a web-based interface to interact with the blockchain across multiple nodes.


## Installation

1. Clone the Repository
```bash
git clone https://github.com/sakthi-1918/P2P-Distributed-blockchain-.git
```
2. Install Dependencies
```bash
pip install -r requirements.txt
```
or
```bash
pip install flask requests
```
## Features

-  Basic blockchain structure (blocks, hashes, proof-of-work)
-  Transactions with validation and balance tracking
-  Peer-to-peer networking with automatic sync and consensus
- Mining with rewards and proof-of-work difficulty
-  Web UI to interact with nodes (send transactions, mine blocks, check balances)
-  Real-time sync indicator (in-sync or out-of-sync with network)


## Usage

1. Start Node 1 (on port 5000)
```bash
python blockchain.py --port 5000
```
2. Start Node 2  and Node 3(on port 5001, 5002 and connect to peer)
```bash
python blockchain.py --port 5001 --peers http://localhost:5000 

python blockchain.py --port 5002 --peers http://localhost:5000 http://localhost:5001
```
## Workflow
Start two nodes (5000, 5001)

Register each node with the other via UI or CLI

Add a transaction on Node 1

Click "Mine Block" on Node 1

On Node 2, click "Sync Blockchain" or "Run Consensus"

Node 2 will now show the updated chain with the new block and transaction.
##  Demo

[![Watch the demo](https://img.youtube.com/vi/5jTqXO_ltMM/0.jpg)](https://youtu.be/5jTqXO_ltMM)



## Notes
1. Genesis Block: Automatically created when blockchain starts
2. Mining Rewards: Default 10 coins per block (configurable)
3. Network Sync: Automatic synchronization every 10 seconds
4. Peer Discovery: Manual peer registration required
5. Data Persistence: Currently in-memory only (restarts clear data)
