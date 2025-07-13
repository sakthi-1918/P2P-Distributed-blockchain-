#!/usr/bin/env python3
"""
Distributed Blockchain Implementation with Flask
A complete blockchain system with multiple nodes, consensus, and web interface.
Enhanced with auto-refresh status and visual blockchain display.
"""

import hashlib
import json
import time
import requests
from flask import Flask, request, jsonify, render_template_string
from urllib.parse import urlparse
import threading
import argparse
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Transaction:
    def __init__(self, sender, receiver, amount, timestamp=None):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.timestamp = timestamp or time.time()
    
    def to_dict(self):
        return {
            'sender': self.sender,
            'receiver': self.receiver,
            'amount': self.amount,
            'timestamp': self.timestamp
        }
    
    def is_valid(self):
        """Basic transaction validation"""
        if self.amount <= 0:
            return False
        if self.sender == self.receiver:
            return False
        if not self.sender or not self.receiver:
            return False
        return True

class Block:
    def __init__(self, index, transactions, previous_hash, timestamp=None):
        self.index = index
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.timestamp = timestamp or time.time()
        self.nonce = 0
        self.hash = self.calculate_hash()
    
    def calculate_hash(self):
        """Calculate the hash of the block"""
        block_string = json.dumps({
            'index': self.index,
            'transactions': [tx.to_dict() for tx in self.transactions],
            'previous_hash': self.previous_hash,
            'timestamp': self.timestamp,
            'nonce': self.nonce
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def mine_block(self, difficulty):
        """Mine the block with proof-of-work"""
        target = "0" * difficulty
        start_time = time.time()
        
        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()
            
            # Add periodic logging for mining progress
            if self.nonce % 10000 == 0:
                logger.info(f"Mining block {self.index}: nonce {self.nonce}")
        
        mining_time = time.time() - start_time
        logger.info(f"Block {self.index} mined in {mining_time:.2f}s with nonce {self.nonce}")
    
    def to_dict(self):
        return {
            'index': self.index,
            'transactions': [tx.to_dict() for tx in self.transactions],
            'previous_hash': self.previous_hash,
            'timestamp': self.timestamp,
            'nonce': self.nonce,
            'hash': self.hash
        }
    
    @classmethod
    def from_dict(cls, data):
        transactions = [Transaction(tx['sender'], tx['receiver'], tx['amount'], tx['timestamp']) 
                       for tx in data['transactions']]
        block = cls(data['index'], transactions, data['previous_hash'], data['timestamp'])
        block.nonce = data['nonce']
        block.hash = data['hash']
        return block

class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]
        self.difficulty = 2
        self.pending_transactions = []
        self.mining_reward = 10
        self.balances = {}
    
    def create_genesis_block(self):
        """Create the first block in the blockchain"""
        return Block(0, [], "0")
    
    def get_latest_block(self):
        return self.chain[-1]
    
    def add_transaction(self, transaction):
        """Add a transaction to the pending transactions"""
        if transaction.is_valid():
            # Check if sender has sufficient balance (except for mining rewards)
            if transaction.sender != "System":
                sender_balance = self.get_balance(transaction.sender)
                if sender_balance < transaction.amount:
                    return False, "Insufficient balance"
            
            self.pending_transactions.append(transaction)
            return True, "Transaction added successfully"
        return False, "Invalid transaction"
    
    def mine_pending_transactions(self, mining_reward_address):
        """Mine all pending transactions"""
        # Add mining reward transaction
        reward_transaction = Transaction("System", mining_reward_address, self.mining_reward)
        self.pending_transactions.append(reward_transaction)
        
        # Create new block
        block = Block(
            len(self.chain),
            self.pending_transactions,
            self.get_latest_block().hash
        )
        
        # Mine the block
        block.mine_block(self.difficulty)
        
        # Add block to chain
        self.chain.append(block)
        
        # Update balances
        self.update_balances()
        
        # Clear pending transactions
        self.pending_transactions = []
        
        return block
    
    def update_balances(self):
        """Update all account balances from the blockchain"""
        self.balances = {}
        
        for block in self.chain:
            for transaction in block.transactions:
                # Deduct from sender
                if transaction.sender != "System":
                    self.balances[transaction.sender] = self.balances.get(transaction.sender, 0) - transaction.amount
                
                # Add to receiver
                self.balances[transaction.receiver] = self.balances.get(transaction.receiver, 0) + transaction.amount
    
    def get_balance(self, address):
        """Get the balance of a specific address"""
        return self.balances.get(address, 0)
    
    def is_chain_valid(self):
        """Validate the entire blockchain"""
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]
            
            # Check if current block hash is valid
            if current_block.hash != current_block.calculate_hash():
                return False
            
            # Check if current block points to previous block
            if current_block.previous_hash != previous_block.hash:
                return False
        
        return True
    
    def to_dict(self):
        return {
            'chain': [block.to_dict() for block in self.chain],
            'difficulty': self.difficulty,
            'pending_transactions': [tx.to_dict() for tx in self.pending_transactions],
            'mining_reward': self.mining_reward
        }
    
    @classmethod
    def from_dict(cls, data):
        blockchain = cls()
        blockchain.chain = [Block.from_dict(block_data) for block_data in data['chain']]
        blockchain.difficulty = data['difficulty']
        blockchain.pending_transactions = [
            Transaction(tx['sender'], tx['receiver'], tx['amount'], tx['timestamp'])
            for tx in data['pending_transactions']
        ]
        blockchain.mining_reward = data['mining_reward']
        blockchain.update_balances()
        return blockchain

class Node:
    def __init__(self, port):
        self.port = port
        self.blockchain = Blockchain()
        self.peers = set()
        self.node_id = f"node_{port}"
        self.app = Flask(__name__)
        self.setup_routes()
    
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            return render_template_string(HTML_TEMPLATE, 
                                        node_id=self.node_id,
                                        port=self.port)
        
        @self.app.route('/blockchain')
        def get_blockchain():
            return jsonify(self.blockchain.to_dict())
        
        @self.app.route('/mine', methods=['POST'])
        def mine_block():
            miner_address = request.json.get('miner_address', self.node_id)
            block = self.blockchain.mine_pending_transactions(miner_address)
            
            # Broadcast new block to peers
            self.broadcast_block(block)
            
            return jsonify({
                'message': 'Block mined successfully',
                'block': block.to_dict()
            })
        
        @self.app.route('/transaction', methods=['POST'])
        def add_transaction():
            data = request.json
            transaction = Transaction(
                data['sender'],
                data['receiver'],
                float(data['amount'])
            )
            
            success, message = self.blockchain.add_transaction(transaction)
            
            if success:
                # Broadcast transaction to peers
                self.broadcast_transaction(transaction)
                return jsonify({'message': message})
            else:
                return jsonify({'error': message}), 400
        
        @self.app.route('/balance/<address>')
        def get_balance(address):
            balance = self.blockchain.get_balance(address)
            return jsonify({'address': address, 'balance': balance})
        
        @self.app.route('/peers')
        def get_peers():
            return jsonify(list(self.peers))
        
        @self.app.route('/register_peer', methods=['POST'])
        def register_peer():
            peer_url = request.json.get('peer_url')
            if peer_url:
                self.peers.add(peer_url)
                return jsonify({'message': 'Peer registered successfully'})
            return jsonify({'error': 'Invalid peer URL'}), 400
        
        @self.app.route('/sync')
        def sync_blockchain():
            self.sync_with_peers()
            return jsonify({'message': 'Blockchain synced'})
        
        @self.app.route('/consensus')
        def consensus():
            replaced = self.resolve_conflicts()
            if replaced:
                return jsonify({'message': 'Blockchain was replaced'})
            return jsonify({'message': 'Blockchain is authoritative'})
        
        @self.app.route('/receive_block', methods=['POST'])
        def receive_block():
            block_data = request.json
            block = Block.from_dict(block_data)
            
            # Validate and add block
            if self.validate_and_add_block(block):
                return jsonify({'message': 'Block accepted'})
            return jsonify({'error': 'Block rejected'}), 400
        
        @self.app.route('/receive_transaction', methods=['POST'])
        def receive_transaction():
            tx_data = request.json
            transaction = Transaction(
                tx_data['sender'],
                tx_data['receiver'],
                tx_data['amount'],
                tx_data['timestamp']
            )
            
            success, message = self.blockchain.add_transaction(transaction)
            return jsonify({'message': message})
        
        @self.app.route('/status')
        def get_status():
            out_of_sync = False

            for peer in self.peers:
                try:
                    response = requests.get(f"{peer}/blockchain", timeout=5)
                    if response.status_code == 200:
                        peer_chain = Blockchain.from_dict(response.json())
                        if len(peer_chain.chain) > len(self.blockchain.chain):
                            out_of_sync = True
                            break
                except:
                    continue

            return jsonify({
                'node_id': self.node_id,
                'port': self.port,
                'chain_length': len(self.blockchain.chain),
                'peers': list(self.peers),
                'pending_transactions': len(self.blockchain.pending_transactions),
                'last_block_hash': self.blockchain.get_latest_block().hash,
                'out_of_sync': out_of_sync
            })

    
    def broadcast_block(self, block):
        """Broadcast a new block to all peers"""
        for peer in self.peers:
            try:
                requests.post(f"{peer}/receive_block", 
                            json=block.to_dict(), 
                            timeout=5)
            except:
                logger.warning(f"Failed to broadcast block to {peer}")
    
    def broadcast_transaction(self, transaction):
        """Broadcast a new transaction to all peers"""
        for peer in self.peers:
            try:
                requests.post(f"{peer}/receive_transaction", 
                            json=transaction.to_dict(), 
                            timeout=5)
            except:
                logger.warning(f"Failed to broadcast transaction to {peer}")
    
    def validate_and_add_block(self, block):
        """Validate and add a received block"""
        # Basic validation
        if block.index != len(self.blockchain.chain):
            return False
        
        if block.previous_hash != self.blockchain.get_latest_block().hash:
            return False
        
        if block.hash != block.calculate_hash():
            return False
        
        # Add block to chain
        self.blockchain.chain.append(block)
        self.blockchain.update_balances()
        
        return True
    
    def sync_with_peers(self):
        """Sync blockchain with peers"""
        for peer in self.peers:
            try:
                response = requests.get(f"{peer}/blockchain", timeout=10)
                if response.status_code == 200:
                    peer_blockchain = Blockchain.from_dict(response.json())
                    
                    # Replace if peer chain is longer and valid
                    if (len(peer_blockchain.chain) > len(self.blockchain.chain) and 
                        peer_blockchain.is_chain_valid()):
                        self.blockchain = peer_blockchain
                        logger.info(f"Blockchain updated from peer {peer}")
            except:
                logger.warning(f"Failed to sync with peer {peer}")
    
    def resolve_conflicts(self):
        """Consensus algorithm: longest chain wins"""
        longest_chain = None
        max_length = len(self.blockchain.chain)
        
        for peer in self.peers:
            try:
                response = requests.get(f"{peer}/blockchain", timeout=10)
                if response.status_code == 200:
                    peer_blockchain = Blockchain.from_dict(response.json())
                    
                    if (len(peer_blockchain.chain) > max_length and 
                        peer_blockchain.is_chain_valid()):
                        max_length = len(peer_blockchain.chain)
                        longest_chain = peer_blockchain
            except:
                logger.warning(f"Failed to get blockchain from peer {peer}")
        
        if longest_chain:
            self.blockchain = longest_chain
            return True
        
        return False
    
    def register_with_peer(self, peer_url):
        """Register this node with a peer"""
        try:
            response = requests.post(f"{peer_url}/register_peer", 
                                   json={'peer_url': f"http://localhost:{self.port}"})
            if response.status_code == 200:
                self.peers.add(peer_url)
                logger.info(f"Registered with peer {peer_url}")
                return True
        except:
            logger.warning(f"Failed to register with peer {peer_url}")
        return False
    
    def run(self, debug=False):
        """Run the Flask application"""
        self.app.run(host='0.0.0.0', port=self.port, debug=debug)

# Enhanced HTML Template with auto-refresh and visual blockchain
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Blockchain Node {{ node_id }}</title>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container { 
            max-width: 1400px; 
            margin: 0 auto; 
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
        }
        .section { 
            margin: 20px 0; 
            padding: 25px; 
            border: none;
            border-radius: 10px; 
            background: #f8f9fa;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .section h2 {
            color: #34495e;
            margin-top: 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
        }
        .form-group { margin: 15px 0; }
        .form-group label { 
            display: block; 
            margin-bottom: 8px; 
            font-weight: bold;
            color: #2c3e50;
        }
        .form-group input { 
            width: 100%; 
            max-width: 300px;
            padding: 10px; 
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        .form-group input:focus {
            outline: none;
            border-color: #3498db;
        }
        button { 
            padding: 12px 24px; 
            background: linear-gradient(45deg, #3498db, #2980b9);
            color: white; 
            border: none; 
            border-radius: 5px;
            cursor: pointer; 
            font-size: 14px;
            font-weight: bold;
            margin: 5px;
            transition: all 0.3s ease;
        }
        button:hover { 
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .blockchain-visual { 
            display: flex;
            overflow-x: auto;
            padding: 20px 0;
            gap: 20px;
        }
        .block {
            min-width: 300px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
            padding: 20px;
            color: white;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
            position: relative;
            transition: transform 0.3s ease;
        }
        .block:hover {
            transform: scale(1.05);
        }
        .block.genesis {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        .block-header {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
            text-align: center;
        }
        .block-content {
            font-size: 12px;
            line-height: 1.4;
        }
        .block-hash {
            font-family: monospace;
            font-size: 10px;
            word-break: break-all;
            background: rgba(255,255,255,0.2);
            padding: 5px;
            border-radius: 3px;
            margin: 5px 0;
        }
        .transactions {
            background: rgba(255,255,255,0.1);
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            max-height: 150px;
            overflow-y: auto;
        }
        .transaction {
            background: rgba(255,255,255,0.1);
            padding: 8px;
            border-radius: 3px;
            margin: 5px 0;
            font-size: 11px;
        }
        .arrow {
            display: flex;
            align-items: center;
            color: #3498db;
            font-size: 24px;
            font-weight: bold;
        }
        .status { 
            padding: 15px; 
            border-radius: 8px; 
            margin: 10px 0;
            font-size: 14px;
        }
        .status.ok {
            background: linear-gradient(135deg, #d4edda, #c3e6cb);
            border: 1px solid #28a745;
            color: #155724;
        }
        .status.warning {
            background: linear-gradient(135deg, #fff3cd, #ffeaa7);
            border: 1px solid #ffc107;
            color: #856404;
        }
        .error { color: #e74c3c; font-weight: bold; }
        .success { color: #27ae60; font-weight: bold; }
        .loading {
            text-align: center;
            color: #7f8c8d;
            font-style: italic;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .stat-number {
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .stat-label {
            font-size: 0.9em;
            opacity: 0.9;
        }
        .pulse {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔗 Blockchain Node {{ node_id }}</h1>
        
        <div class="section">
            <h2>📊 Node Status</h2>
            <div id="status" class="status loading">Loading status...</div>
            <div id="stats" class="stats-grid"></div>
        </div>
        
        <div class="section">
            <h2>💰 Add Transaction</h2>
            <div class="form-group">
                <label>Sender:</label>
                <input type="text" id="sender" placeholder="Enter sender address">
            </div>
            <div class="form-group">
                <label>Receiver:</label>
                <input type="text" id="receiver" placeholder="Enter receiver address">
            </div>
            <div class="form-group">
                <label>Amount:</label>
                <input type="number" id="amount" placeholder="Enter amount" step="0.01">
            </div>
            <button onclick="addTransaction()">Add Transaction</button>
            <div id="transactionResult"></div>
        </div>
        
        <div class="section">
            <h2>⛏️ Mining</h2>
            <div class="form-group">
                <label>Miner Address:</label>
                <input type="text" id="minerAddress" value="{{ node_id }}" placeholder="Enter miner address">
            </div>
            <button onclick="mineBlock()">Mine Block</button>
            <div id="miningResult"></div>
        </div>
        
        <div class="section">
            <h2>💳 Check Balance</h2>
            <div class="form-group">
                <label>Address:</label>
                <input type="text" id="balanceAddress" placeholder="Enter address">
            </div>
            <button onclick="checkBalance()">Check Balance</button>
            <div id="balanceResult"></div>
        </div>
        
        <div class="section">
            <h2>🌐 Peer Management</h2>
            <div class="form-group">
                <label>Peer URL:</label>
                <input type="text" id="peerUrl" placeholder="http://localhost:5001">
            </div>
            <button onclick="registerPeer()">Register Peer</button>
            <button onclick="syncBlockchain()">Sync Blockchain</button>
            <button onclick="runConsensus()">Run Consensus</button>
            <div id="peerResult"></div>
        </div>
        
        <div class="section">
            <h2>⛓️ Blockchain Visualization</h2>
            <div id="blockchainVisual" class="blockchain-visual">
                <div class="loading">Loading blockchain...</div>
            </div>
        </div>
    </div>

    <script>
        // Auto-refresh status every 5 seconds
        function loadStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    const statusDiv = document.getElementById('status');
                    const statsDiv = document.getElementById('stats');

                    // Apply conditional color class
                    if (data.out_of_sync) {
                        statusDiv.className = 'status warning';
                    } else {
                        statusDiv.className = 'status ok';
                    }

                    // Fill in the status content
                    statusDiv.innerHTML = `
                        ${data.out_of_sync ? "<p><strong>⚠️ Node is out of sync!</strong></p>" : "<p><strong>✅ Node is synchronized</strong></p>"}
                        <strong>Node ID:</strong> ${data.node_id}<br>
                        <strong>Port:</strong> ${data.port}<br>
                        <strong>Peers:</strong> ${data.peers.length > 0 ? data.peers.join(', ') : 'No peers connected'}<br>
                        <strong>Last Block Hash:</strong> <span style="font-family: monospace;">${data.last_block_hash.substring(0, 16)}...</span>
                    `;

                    // Create stats cards
                    statsDiv.innerHTML = `
                        <div class="stat-card">
                            <div class="stat-number">${data.chain_length}</div>
                            <div class="stat-label">Blocks</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.pending_transactions}</div>
                            <div class="stat-label">Pending Transactions</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.peers.length}</div>
                            <div class="stat-label">Connected Peers</div>
                        </div>
                    `;
                })
                .catch(error => {
                    document.getElementById('status').innerHTML = 
                        '<p class="error">Failed to load status</p>';
                });
        }

        // Load and visualize blockchain
        function loadBlockchainVisual() {
            fetch('/blockchain')
                .then(response => response.json())
                .then(data => {
                    const visualDiv = document.getElementById('blockchainVisual');
                    let html = '';
                    
                    data.chain.forEach((block, index) => {
                        const blockClass = index === 0 ? 'block genesis' : 'block';
                        const blockTime = new Date(block.timestamp * 1000).toLocaleString();
                        
                        html += `
                            <div class="${blockClass}">
                                <div class="block-header">
                                    ${index === 0 ? ' 📦Genesis Block' : `📦 Block #${block.index}`}
                                </div>
                                <div class="block-content">
                                    <div><strong>Timestamp:</strong> ${blockTime}</div>
                                    <div><strong>Nonce:</strong> ${block.nonce}</div>
                                    <div class="block-hash">
                                        <strong>Hash:</strong><br>${block.hash}
                                    </div>
                                    <div class="block-hash">
                                        <strong>Previous Hash:</strong><br>${block.previous_hash}
                                    </div>
                                    <div class="transactions">
                                        <strong>Transactions (${block.transactions.length}):</strong>
                                        ${block.transactions.map(tx => `
                                            <div class="transaction">
                                                <strong>${tx.sender}</strong> → <strong>${tx.receiver}</strong><br>
                                                Amount: ${tx.amount} coins
                                            </div>
                                        `).join('')}
                                        ${block.transactions.length === 0 ? '<div class="transaction">No transactions</div>' : ''}
                                    </div>
                                </div>
                            </div>
                        `;
                        
                        // Add arrow between blocks (except for the last block)
                        if (index < data.chain.length - 1) {
                            html += '<div class="arrow">→</div>';
                        }
                    });
                    
                    visualDiv.innerHTML = html;
                })
                .catch(error => {
                    document.getElementById('blockchainVisual').innerHTML = 
                        '<p class="error">Failed to load blockchain</p>';
                });
        }
        
        // Add transaction
        function addTransaction() {
            const sender = document.getElementById('sender').value;
            const receiver = document.getElementById('receiver').value;
            const amount = document.getElementById('amount').value;
            
            if (!sender || !receiver || !amount) {
                document.getElementById('transactionResult').innerHTML = 
                    '<p class="error">Please fill in all fields</p>';
                return;
            }
            
            fetch('/transaction', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sender, receiver, amount })
            })
            .then(response => response.json())
            .then(data => {
                const resultDiv = document.getElementById('transactionResult');
                if (data.message) {
                    resultDiv.innerHTML = `<p class="success">✅ ${data.message}</p>`;
                    // Clear form
                    document.getElementById('sender').value = '';
                    document.getElementById('receiver').value = '';
                    document.getElementById('amount').value = '';
                } else {
                    resultDiv.innerHTML = `<p class="error">❌ ${data.error}</p>`;
                }
            });
        }
        
        // Mine block
        function mineBlock() {
            const minerAddress = document.getElementById('minerAddress').value;
            const button = event.target;
            const originalText = button.textContent;
            
            button.textContent = 'Mining...';
            button.disabled = true;
            button.classList.add('pulse');
            
            fetch('/mine', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ miner_address: minerAddress })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('miningResult').innerHTML = 
                    `<p class="success">⛏️ ${data.message}</p>`;
                loadBlockchainVisual(); // Refresh blockchain visualization
            })
            .catch(error => {
                document.getElementById('miningResult').innerHTML = 
                    `<p class="error">❌ Mining failed</p>`;
            })
            .finally(() => {
                button.textContent = originalText;
                button.disabled = false;
                button.classList.remove('pulse');
            });
        }
        
        // Check balance
        function checkBalance() {
            const address = document.getElementById('balanceAddress').value;
            
            if (!address) {
                document.getElementById('balanceResult').innerHTML = 
                    '<p class="error">Please enter an address</p>';
                return;
            }
            
            fetch(`/balance/${address}`)
                .then(response => response.json())
                .then(data => {
                    document.getElementById('balanceResult').innerHTML = 
                        `<p class="success">💰 Balance: <strong>${data.balance} coins</strong></p>`;
                });
        }
        
        // Register peer
        function registerPeer() {
            const peerUrl = document.getElementById('peerUrl').value;
            
            if (!peerUrl) {
                document.getElementById('peerResult').innerHTML = 
                    '<p class="error">Please enter a peer URL</p>';
                return;
            }
            
            fetch('/register_peer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ peer_url: peerUrl })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('peerResult').innerHTML = 
                    `<p class="success">🤝 ${data.message}</p>`;
                document.getElementById('peerUrl').value = '';
            })
            .catch(error => {
                document.getElementById('peerResult').innerHTML = 
                    `<p class="error">❌ Failed to register peer</p>`;
            });
        }
        
        // Sync blockchain
        function syncBlockchain() {
            const button = event.target;
            const originalText = button.textContent;
            
            button.textContent = 'Syncing...';
            button.disabled = true;
            button.classList.add('pulse');
            
            fetch('/sync')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('peerResult').innerHTML = 
                        `<p class="success">🔄 ${data.message}</p>`;
                    loadBlockchainVisual(); // Refresh blockchain visualization
                })
                .catch(error => {
                    document.getElementById('peerResult').innerHTML = 
                        `<p class="error">❌ Sync failed</p>`;
                })
                .finally(() => {
                    button.textContent = originalText;
                    button.disabled = false;
                    button.classList.remove('pulse');
                });
        }
        
        // Run consensus
        function runConsensus() {
            const button = event.target;
            const originalText = button.textContent;
            
            button.textContent = 'Running Consensus...';
            button.disabled = true;
            button.classList.add('pulse');
            
            fetch('/consensus')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('peerResult').innerHTML = 
                        `<p class="success">🎯 ${data.message}</p>`;
                    loadBlockchainVisual(); // Refresh blockchain visualization
                })
                .catch(error => {
                    document.getElementById('peerResult').innerHTML = 
                        `<p class="error">❌ Consensus failed</p>`;
                })
                .finally(() => {
                    button.textContent = originalText;
                    button.disabled = false;
                    button.classList.remove('pulse');
                });
        }
        
        // Auto-refresh functions
        function startAutoRefresh() {
            // Load initial data
            loadStatus();
            loadBlockchainVisual();
            
            // Set up auto-refresh intervals
            setInterval(loadStatus, 5000); // Refresh status every 5 seconds
            setInterval(loadBlockchainVisual, 10000); // Refresh blockchain every 10 seconds
        }
        
        // Initialize when page loads
        window.onload = function() {
            startAutoRefresh();
        };
        
        // Add keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey || e.metaKey) {
                switch(e.key) {
                    case 'Enter':
                        if (document.activeElement.id === 'amount') {
                            addTransaction();
                        } else if (document.activeElement.id === 'minerAddress') {
                            mineBlock();
                        } else if (document.activeElement.id === 'balanceAddress') {
                            checkBalance();
                        } else if (document.activeElement.id === 'peerUrl') {
                            registerPeer();
                        }
                        break;
                }
            }
        });
        
        // Add Enter key support for forms
        document.getElementById('sender').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') addTransaction();
        });
        document.getElementById('receiver').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') addTransaction();
        });
        document.getElementById('amount').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') addTransaction();
        });
        document.getElementById('minerAddress').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') mineBlock();
        });
        document.getElementById('balanceAddress').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') checkBalance();
        });
        document.getElementById('peerUrl').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') registerPeer();
        });
    </script>
</body>
</html>
"""

def main():
    parser = argparse.ArgumentParser(description='Run a blockchain node')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the node on')
    parser.add_argument('--peers', nargs='*', help='List of peer URLs to connect to')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    
    args = parser.parse_args()
    
    # Create and configure node
    node = Node(args.port)
    
    # Register with peers if provided
    if args.peers:
        for peer in args.peers:
            node.register_with_peer(peer)
        
        # Sync blockchain from peers
        node.sync_with_peers()
    
    print(f"Starting blockchain node on port {args.port}")
    print(f"Web interface available at http://localhost:{args.port}")
    
    # Run the node
    node.run(debug=args.debug)

if __name__ == '__main__':
    main()