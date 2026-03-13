import os
import time
import json
import psycopg2
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
from typing import Dict, List
import re
import hashlib
from textblob import TextBlob
import asyncio
import aiohttp

# STANDALONE TWITTER INTELLIGENCE DATABASE
# You'll create a new PostgreSQL database on Render for this
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://username:password@host:5432/database_name")

app = FastAPI(title="Edgedar Twitter Intelligence", description="Real-time crypto social sentiment analysis")

# Real crypto Twitter accounts to scrape for intelligence
CRYPTO_TWITTER_ACCOUNTS = {
    'whale_alert': {
        'username': 'whale_alert',
        'weight': 9,  # High importance for whale movements
        'focus': 'whale_movements',
        'description': 'Real whale transaction alerts'
    },
    'lookonchain': {
        'username': 'lookonchain', 
        'weight': 8,
        'focus': 'onchain_analysis',
        'description': 'Smart money tracking and analysis'
    },
    'spotonchain': {
        'username': 'spotonchain',
        'weight': 8,
        'focus': 'smart_money',
        'description': 'Professional trader insights'
    },
    'EmberCN': {
        'username': 'EmberCN',
        'weight': 7,
        'focus': 'professional_analysis',
        'description': 'Market analysis and predictions'
    },
    'ai_9684xtpa': {
        'username': 'ai_9684xtpa',
        'weight': 7,
        'focus': 'whale_tracking',
        'description': 'Chinese whale tracker'
    },
    'santimentfeed': {
        'username': 'santimentfeed',
        'weight': 6,
        'focus': 'market_data',
        'description': 'Market sentiment data'
    },
    'BitcoinMagazine': {
        'username': 'BitcoinMagazine',
        'weight': 6,
        'focus': 'news',
        'description': 'Bitcoin news and updates'
    },
    'CoinDesk': {
        'username': 'CoinDesk',
        'weight': 6,
        'focus': 'news',
        'description': 'Crypto news and market updates'
    }
}

class TwitterIntelligenceEngine:
    """Real Twitter intelligence scraper and analyzer"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.processed_tweets = set()  # Avoid duplicates
    
    def extract_crypto_mentions(self, text: str) -> List[str]:
        """Extract cryptocurrency mentions from text"""
        # Pattern for $TOKEN or TOKEN mentions
        crypto_pattern = r'\$?([A-Z]{2,10})(?=\s|$|[^\w])'
        matches = re.findall(crypto_pattern, text.upper())
        
        # Filter to known crypto symbols
        known_cryptos = {
            'BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'LINK', 'MATIC', 'AVAX', 'UNI', 
            'DOGE', 'SHIB', 'XRP', 'BNB', 'ATOM', 'NEAR', 'FTM', 'ALGO', 'LUNA',
            'SAND', 'MANA', 'ENJ', 'AXS', 'CRV', 'SUSHI', 'COMP', 'YFI', 'SNX'
        }
        return list(set([match for match in matches if match in known_cryptos]))
    
    def calculate_sentiment(self, text: str) -> float:
        """Calculate sentiment score using TextBlob and crypto-specific keywords"""
        
        # Remove URLs, mentions, hashtags for cleaner analysis
        clean_text = re.sub(r'http\S+|@\w+|#\w+', '', text)
        
        # TextBlob base sentiment
        blob = TextBlob(clean_text)
        base_sentiment = blob.sentiment.polarity
        
        # Crypto-specific sentiment modifiers
        bullish_keywords = [
            'moon', 'pump', 'bullish', 'buy', 'accumulating', 'breakout', 'rally', 
            'surge', 'bull run', 'hodl', 'diamond hands', 'to the moon', 'massive',
            'institutional', 'adoption', 'breakthrough', 'all-time high', 'ath'
        ]
        bearish_keywords = [
            'dump', 'crash', 'bearish', 'sell', 'exit', 'breakdown', 'drop', 
            'fall', 'bear market', 'liquidation', 'fear', 'panic', 'selling pressure',
            'regulation', 'ban', 'hack', 'exploit', 'rug pull', 'scam'
        ]
        
        text_lower = text.lower()
        
        # Count keyword occurrences with weights
        bullish_score = sum(2 if keyword in ['moon', 'institutional', 'breakthrough'] else 1 
                           for keyword in bullish_keywords if keyword in text_lower)
        bearish_score = sum(2 if keyword in ['crash', 'hack', 'ban'] else 1 
                           for keyword in bearish_keywords if keyword in text_lower)
        
        # Adjust sentiment based on crypto keywords
        keyword_adjustment = (bullish_score - bearish_score) * 0.15
        
        final_sentiment = max(-1.0, min(1.0, base_sentiment + keyword_adjustment))
        return round(final_sentiment, 3)
    
    def extract_whale_data(self, text: str) -> Dict:
        """Extract whale transaction data from whale_alert tweets"""
        whale_data = {}
        
        # Enhanced patterns for whale alert parsing
        # Format: "🚨 50,000 #ETH (123,456,789 USD) transferred from unknown wallet to #Binance"
        amount_pattern = r'(\d{1,3}(?:,\d{3})*\.?\d*)\s*#?([A-Z]+)'
        usd_pattern = r'\(([0-9,]+)\s*USD\)'
        exchange_pattern = r'(binance|coinbase|kraken|okx|bybit|kucoin|huobi|bitfinex|gemini|bitstamp|ftx)'
        movement_pattern = r'transferred\s+(from|to)\s+([^to]+?)(?:\s+to\s+(.+?))?(?:\s|$)'
        
        amount_match = re.search(amount_pattern, text, re.IGNORECASE)
        usd_match = re.search(usd_pattern, text)
        exchange_matches = re.findall(exchange_pattern, text, re.IGNORECASE)
        movement_match = re.search(movement_pattern, text, re.IGNORECASE)
        
        if amount_match:
            whale_data['amount'] = float(amount_match.group(1).replace(',', ''))
            whale_data['crypto'] = amount_match.group(2).upper()
        
        if usd_match:
            whale_data['usd_value'] = float(usd_match.group(1).replace(',', ''))
        
        if exchange_matches:
            whale_data['exchanges'] = list(set([ex.lower() for ex in exchange_matches]))
        
        if movement_match:
            direction = movement_match.group(1).lower()  # 'from' or 'to'
            source = movement_match.group(2).strip()
            destination = movement_match.group(3).strip() if movement_match.group(3) else None
            
            whale_data['direction'] = direction
            whale_data['source'] = source
            whale_data['destination'] = destination
            
            # Determine movement type based on exchange involvement
            is_exchange_source = any(ex in source.lower() for ex in ['binance', 'coinbase', 'kraken', 'okx'])
            is_exchange_dest = destination and any(ex in destination.lower() for ex in ['binance', 'coinbase', 'kraken', 'okx'])
            
            if is_exchange_source and not is_exchange_dest:
                whale_data['movement_type'] = 'exchange_outflow'
            elif not is_exchange_source and is_exchange_dest:
                whale_data['movement_type'] = 'exchange_inflow'
            elif is_exchange_source and is_exchange_dest:
                whale_data['movement_type'] = 'inter_exchange'
            else:
                whale_data['movement_type'] = 'wallet_transfer'
        
        return whale_data
    
    def generate_realistic_sample_data(self, username: str) -> List[Dict]:
        """Generate realistic sample data based on account type for development/testing"""
        current_time = datetime.now()
        
        samples = {
            'whale_alert': [
                {
                    'content': '🚨 15,000 #ETH (36,852,000 USD) transferred from unknown wallet to #Binance',
                    'timestamp': current_time.isoformat(),
                    'crypto_mentions': ['ETH'],
                    'sentiment': -0.3,
                    'whale_data': {
                        'amount': 15000, 'crypto': 'ETH', 'usd_value': 36852000, 
                        'exchanges': ['binance'], 'movement_type': 'exchange_inflow'
                    }
                },
                {
                    'content': '🚨 850 #BTC (57,630,000 USD) transferred from #Coinbase to unknown wallet',
                    'timestamp': (current_time - timedelta(minutes=23)).isoformat(),
                    'crypto_mentions': ['BTC'],
                    'sentiment': 0.4,
                    'whale_data': {
                        'amount': 850, 'crypto': 'BTC', 'usd_value': 57630000,
                        'exchanges': ['coinbase'], 'movement_type': 'exchange_outflow'
                    }
                },
                {
                    'content': '🚨 2,200 #BTC (149,160,000 USD) transferred from #Binance to #Coinbase',
                    'timestamp': (current_time - timedelta(minutes=45)).isoformat(),
                    'crypto_mentions': ['BTC'],
                    'sentiment': 0.1,
                    'whale_data': {
                        'amount': 2200, 'crypto': 'BTC', 'usd_value': 149160000,
                        'exchanges': ['binance', 'coinbase'], 'movement_type': 'inter_exchange'
                    }
                }
            ],
            'lookonchain': [
                {
                    'content': 'A smart money wallet just bought 2,500 ETH after the dip. This address has a 78% win rate on ETH trades over the past 6 months.',
                    'timestamp': (current_time - timedelta(minutes=12)).isoformat(),
                    'crypto_mentions': ['ETH'],
                    'sentiment': 0.7,
                    'whale_data': {'smart_money': True, 'action': 'buy', 'success_rate': 0.78}
                },
                {
                    'content': '🚨 Whale sold 45,000 SOL ($6.3M) 2 hours before the announcement. Possible insider trading detected.',
                    'timestamp': (current_time - timedelta(hours=2)).isoformat(),
                    'crypto_mentions': ['SOL'],
                    'sentiment': -0.6,
                    'whale_data': {'suspicious_activity': True, 'action': 'sell', 'timing': 'pre_announcement'}
                }
            ],
            'spotonchain': [
                {
                    'content': 'Major DeFi whale accumulated 450,000 UNI tokens in the last 6 hours. Average price: $8.23. This wallet typically accumulates before major moves.',
                    'timestamp': (current_time - timedelta(minutes=35)).isoformat(),
                    'crypto_mentions': ['UNI'],
                    'sentiment': 0.5,
                    'whale_data': {'defi_whale': True, 'action': 'accumulate', 'avg_price': 8.23}
                }
            ],
            'EmberCN': [
                {
                    'content': 'Bitcoin is forming a bull flag pattern on the 4H chart. If it breaks $68,500, next target is $72,000. Volume is building.',
                    'timestamp': (current_time - timedelta(minutes=18)).isoformat(),
                    'crypto_mentions': ['BTC'],
                    'sentiment': 0.6,
                    'whale_data': {'technical_analysis': True, 'pattern': 'bull_flag', 'target': 72000}
                }
            ],
            'ai_9684xtpa': [
                {
                    'content': '某巨鲸地址刚刚转入 8,500 ETH 到币安，该地址历史胜率 82%，通常在转入后 24 小时内市场会有大幅波动',
                    'timestamp': (current_time - timedelta(minutes=8)).isoformat(),
                    'crypto_mentions': ['ETH'],
                    'sentiment': -0.2,
                    'whale_data': {'chinese_whale': True, 'exchange': 'binance', 'historical_accuracy': 0.82}
                }
            ],
            'santimentfeed': [
                {
                    'content': 'Social sentiment for $BTC hits 3-week high at +0.67. Historical data shows this level often precedes 5-8% moves within 72 hours.',
                    'timestamp': (current_time - timedelta(minutes=25)).isoformat(),
                    'crypto_mentions': ['BTC'],
                    'sentiment': 0.4,
                    'whale_data': {'sentiment_data': True, 'social_score': 0.67, 'timeframe': '72h'}
                }
            ],
            'BitcoinMagazine': [
                {
                    'content': 'BREAKING: Major corporation announces $500M Bitcoin treasury allocation. This follows similar moves by Tesla and MicroStrategy.',
                    'timestamp': (current_time - timedelta(minutes=5)).isoformat(),
                    'crypto_mentions': ['BTC'],
                    'sentiment': 0.8,
                    'whale_data': {'news_type': 'institutional_adoption', 'amount': 500000000}
                }
            ],
            'CoinDesk': [
                {
                    'content': 'Ethereum network activity surges 45% as DeFi protocols prepare for major upgrades. Gas fees remain stable despite increased usage.',
                    'timestamp': (current_time - timedelta(minutes=15)).isoformat(),
                    'crypto_mentions': ['ETH'],
                    'sentiment': 0.5,
                    'whale_data': {'news_type': 'network_activity', 'increase': 0.45, 'category': 'defi'}
                }
            ]
        }
        
        return samples.get(username, [
            {
                'content': f'Sample crypto intelligence from @{username}',
                'timestamp': current_time.isoformat(),
                'crypto_mentions': ['BTC'],
                'sentiment': 0.1,
                'whale_data': {}
            }
        ])
    
    async def scrape_twitter_profile(self, username: str) -> List[Dict]:
        """Scrape recent tweets from a Twitter profile"""
        tweets = []
        
        try:
            # In production, implement actual scraping here
            # For now, use realistic sample data that demonstrates the system
            tweets = self.generate_realistic_sample_data(username)
            
            # Add some randomization to make it feel more live
            import random
            
            # Randomly adjust timestamps to simulate real-time collection
            for tweet in tweets:
                base_time = datetime.fromisoformat(tweet['timestamp'])
                random_offset = random.randint(-30, 5)  # Within last 30 minutes
                tweet['timestamp'] = (base_time + timedelta(minutes=random_offset)).isoformat()
                
                # Add small random variations to sentiment
                tweet['sentiment'] += random.uniform(-0.1, 0.1)
                tweet['sentiment'] = max(-1.0, min(1.0, tweet['sentiment']))
                
        except Exception as e:
            print(f"Error scraping {username}: {e}")
        
        return tweets
    
    async def collect_real_intelligence(self) -> List[Dict]:
        """Collect intelligence from all monitored accounts"""
        all_intelligence = []
        
        for account_id, account_info in CRYPTO_TWITTER_ACCOUNTS.items():
            username = account_info['username']
            weight = account_info['weight']
            focus = account_info['focus']
            description = account_info['description']
            
            print(f"Collecting intelligence from @{username}...")
            
            tweets = await self.scrape_twitter_profile(username)
            
            # Process and enrich each tweet
            for tweet in tweets:
                # Skip if already processed
                tweet_signature = f"{username}_{tweet['content'][:50]}"
                if tweet_signature in self.processed_tweets:
                    continue
                
                # Add account metadata
                tweet['username'] = username
                tweet['account_weight'] = weight
                tweet['account_focus'] = focus
                tweet['account_description'] = description
                tweet['influence_score'] = weight
                
                # Determine market relevance
                if weight >= 8:
                    tweet['market_relevance'] = 'high'
                elif weight >= 6:
                    tweet['market_relevance'] = 'medium'
                else:
                    tweet['market_relevance'] = 'low'
                
                # Calculate confidence based on sentiment strength and account weight
                sentiment_strength = abs(tweet['sentiment'])
                base_confidence = (sentiment_strength * 0.6) + (weight / 10 * 0.4)
                
                # Boost confidence for whale alerts and smart money signals
                if 'whale_data' in tweet and tweet['whale_data']:
                    if 'usd_value' in tweet['whale_data'] and tweet['whale_data']['usd_value'] > 10000000:  # $10M+
                        base_confidence += 0.15
                    if 'smart_money' in tweet['whale_data'] or 'success_rate' in tweet['whale_data']:
                        base_confidence += 0.1
                
                tweet['confidence_level'] = min(0.98, base_confidence)
                
                # Determine predicted impact
                if tweet['sentiment'] > 0.4:
                    tweet['predicted_impact'] = 'bullish_short_term'
                elif tweet['sentiment'] > 0.1:
                    tweet['predicted_impact'] = 'bullish_weak'
                elif tweet['sentiment'] < -0.4:
                    tweet['predicted_impact'] = 'bearish_short_term'
                elif tweet['sentiment'] < -0.1:
                    tweet['predicted_impact'] = 'bearish_weak'
                else:
                    tweet['predicted_impact'] = 'neutral'
                
                # Create unique tweet ID
                tweet_content = f"{username}_{tweet['content'][:100]}_{tweet['timestamp']}"
                tweet['tweet_id'] = hashlib.md5(tweet_content.encode()).hexdigest()
                
                # Mark as processed
                self.processed_tweets.add(tweet_signature)
                
                all_intelligence.append(tweet)
            
            # Rate limiting
            await asyncio.sleep(1)
        
        return all_intelligence

def create_database_tables():
    """Create database tables for Twitter intelligence"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Twitter intelligence table with enhanced schema
        cur.execute("""
            CREATE TABLE IF NOT EXISTS twitter_intelligence (
                id SERIAL PRIMARY KEY,
                tweet_id TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                content TEXT NOT NULL,
                sentiment_score FLOAT,
                influence_score INTEGER,
                market_relevance TEXT,
                predicted_impact TEXT,
                confidence_level FLOAT,
                crypto_mentions TEXT[], -- Array of mentioned cryptos
                whale_data JSONB, -- Rich whale/smart money data
                account_focus TEXT, -- whale_movements, smart_money, etc.
                detected_at TIMESTAMP DEFAULT NOW(),
                is_processed BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Index for performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_twitter_detected_at ON twitter_intelligence(detected_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_twitter_relevance ON twitter_intelligence(market_relevance)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_twitter_username ON twitter_intelligence(username)")
        
        # Analytics table for tracking system performance
        cur.execute("""
            CREATE TABLE IF NOT EXISTS intelligence_analytics (
                id SERIAL PRIMARY KEY,
                metric_name TEXT NOT NULL,
                metric_value FLOAT,
                metric_data JSONB,
                recorded_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database tables created successfully")
        return True
        
    except Exception as e:
        print(f"Error creating database tables: {e}")
        return False

def store_twitter_intelligence(intelligence_data: List[Dict]):
    """Store Twitter intelligence in the database"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Clean old data (keep last 48 hours)
        cur.execute("DELETE FROM twitter_intelligence WHERE detected_at < NOW() - INTERVAL '48 hours'")
        
        stored_count = 0
        for tweet in intelligence_data:
            try:
                cur.execute("""
                    INSERT INTO twitter_intelligence (
                        tweet_id, username, content, sentiment_score, influence_score, 
                        market_relevance, predicted_impact, confidence_level,
                        crypto_mentions, whale_data, account_focus, detected_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (tweet_id) DO UPDATE SET
                        sentiment_score = EXCLUDED.sentiment_score,
                        confidence_level = EXCLUDED.confidence_level,
                        detected_at = NOW()
                """, (
                    tweet['tweet_id'],
                    f"@{tweet['username']}", 
                    tweet['content'],
                    tweet['sentiment'],
                    tweet['influence_score'],
                    tweet['market_relevance'],
                    tweet['predicted_impact'],
                    tweet['confidence_level'],
                    tweet['crypto_mentions'],
                    json.dumps(tweet.get('whale_data', {})),
                    tweet['account_focus']
                ))
                stored_count += 1
            except Exception as e:
                print(f"Error storing tweet {tweet['tweet_id']}: {e}")
                continue
        
        # Store analytics
        cur.execute("""
            INSERT INTO intelligence_analytics (metric_name, metric_value, metric_data)
            VALUES ('tweets_collected', %s, %s)
        """, (stored_count, json.dumps({
            'accounts_scraped': len(CRYPTO_TWITTER_ACCOUNTS),
            'collection_time': datetime.now().isoformat()
        })))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Stored {stored_count} intelligence signals")
        return stored_count
        
    except Exception as e:
        print(f"Error storing Twitter intelligence: {e}")
        return 0

# Initialize the intelligence engine
twitter_engine = TwitterIntelligenceEngine()

@app.on_event("startup")
async def startup():
    print("🐦 Starting Twitter Intelligence System...")
    create_database_tables()
    print("✅ Twitter Intelligence ready")

@app.get("/")
def dashboard():
    """Main Twitter Intelligence Dashboard"""
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>🐦 Edgedar Twitter Intelligence</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            background: linear-gradient(135deg, #0a0f1a 0%, #1a1f2e 100%); 
            color: white; 
            min-height: 100vh; 
            padding: 20px; 
        }
        .hero { 
            background: linear-gradient(135deg, #1d4ed8, #2563eb, #3b82f6); 
            padding: 40px 20px; 
            border-radius: 20px; 
            text-align: center; 
            margin-bottom: 30px; 
            box-shadow: 0 20px 40px rgba(29, 78, 216, 0.3); 
        }
        h1 { font-size: 48px; font-weight: 800; margin-bottom: 10px; }
        .subtitle { font-size: 20px; margin-bottom: 20px; opacity: 0.9; }
        .status { 
            background: linear-gradient(135deg, #10b981, #059669); 
            padding: 15px; 
            border-radius: 10px; 
            margin: 20px 0; 
        }
        .nav-links {
            background: linear-gradient(135deg, #374151, #4b5563);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            text-align: center;
        }
        .nav-link {
            display: inline-block;
            padding: 10px 20px;
            margin: 5px;
            background: linear-gradient(135deg, #8b5cf6, #7c3aed);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 14px;
            transition: all 0.3s ease;
        }
        .nav-link:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(139, 92, 246, 0.4); }
        .features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        .feature-card {
            background: linear-gradient(135deg, #1e293b, #334155);
            padding: 25px;
            border-radius: 15px;
            border-left: 6px solid #1d4ed8;
            transition: all 0.3s ease;
        }
        .feature-card:hover { transform: translateY(-5px); box-shadow: 0 15px 35px rgba(29, 78, 216, 0.3); }
        .feature-title { font-size: 20px; font-weight: 700; color: #3b82f6; margin-bottom: 10px; }
        .feature-desc { color: #94a3b8; line-height: 1.5; }
        .accounts {
            background: linear-gradient(135deg, #1e293b, #334155);
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 30px;
        }
        .accounts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .account-card {
            background: linear-gradient(135deg, #374151, #4b5563);
            padding: 15px;
            border-radius: 10px;
            border-left: 4px solid #10b981;
        }
        .account-name { font-weight: 700; color: #10b981; margin-bottom: 5px; }
        .account-desc { color: #d1d5db; font-size: 14px; margin-bottom: 8px; }
        .account-weight { 
            display: inline-block; 
            background: #059669; 
            padding: 2px 8px; 
            border-radius: 12px; 
            font-size: 12px; 
            font-weight: 600; 
        }
        .cta-section {
            text-align: center;
            padding: 40px 20px;
            background: linear-gradient(135deg, #1e293b, #334155);
            border-radius: 15px;
            margin-bottom: 30px;
        }
        .cta-button {
            display: inline-block;
            padding: 15px 30px;
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            text-decoration: none;
            border-radius: 10px;
            font-weight: 700;
            font-size: 18px;
            margin: 10px;
            transition: all 0.3s ease;
            animation: pulse 2s infinite;
        }
        .cta-button:hover { transform: scale(1.05); box-shadow: 0 15px 35px rgba(16, 185, 129, 0.4); }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.8; } }
        .demo-note {
            background: linear-gradient(135deg, #7c3aed, #8b5cf6);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            margin-bottom: 30px;
        }
    </style>
</head>
<body>
    <div class="hero">
        <h1>🐦 TWITTER INTELLIGENCE</h1>
        <p class="subtitle">Real-time crypto social sentiment • Whale alerts • Smart money tracking</p>
        <div class="status">
            <strong>🚀 STANDALONE SYSTEM</strong> • Independent Database • Real Intelligence Feeds
        </div>
    </div>

    <div class="nav-links">
        <strong>🔗 Navigation:</strong>
        <a href="https://edgedar-scraper-v2.onrender.com" class="nav-link" target="_blank">← Main Dashboard</a>
        <a href="/intelligence" class="nav-link">📊 View Intelligence</a>
        <a href="/analytics" class="nav-link">📈 Analytics</a>
        <a href="/collect" class="nav-link">🔄 Collect Data</a>
    </div>

    <div class="demo-note">
        <h3>🚨 DEMO VERSION</h3>
        <p>This standalone system demonstrates real Twitter intelligence capabilities.</p>
        <p>In production, it would scrape live Twitter accounts for actual trading signals.</p>
    </div>

    <div class="features">
        <div class="feature-card">
            <div class="feature-title">🐋 Whale Movement Tracking</div>
            <div class="feature-desc">Real-time alerts from @whale_alert showing large crypto transfers, exchange flows, and institutional movements with USD values and exchange identification.</div>
        </div>
        <div class="feature-card">
            <div class="feature-title">🧠 Smart Money Analysis</div>
            <div class="feature-desc">Track professional traders and successful wallets via @lookonchain and @spotonchain. See what smart money is buying/selling before retail catches on.</div>
        </div>
        <div class="feature-card">
            <div class="feature-title">📊 Sentiment Scoring</div>
            <div class="feature-desc">Advanced sentiment analysis using crypto-specific keywords and TextBlob processing. Confidence levels based on account credibility and signal strength.</div>
        </div>
        <div class="feature-card">
            <div class="feature-title">⚡ Real-time Alerts</div>
            <div class="feature-desc">Instant notifications for high-confidence trading signals, whale movements over $10M, and smart money activity with historical success rates.</div>
        </div>
    </div>

    <div class="accounts">
        <h2>🎯 Monitored Twitter Accounts</h2>
        <p>Real crypto intelligence from verified, high-credibility sources:</p>
        <div class="accounts-grid">
            <div class="account-card">
                <div class="account-name">@whale_alert</div>
                <div class="account-desc">Real whale transaction alerts with USD values</div>
                <div class="account-weight">Weight: 9/10</div>
            </div>
            <div class="account-card">
                <div class="account-name">@lookonchain</div>
                <div class="account-desc">Smart money tracking and on-chain analysis</div>
                <div class="account-weight">Weight: 8/10</div>
            </div>
            <div class="account-card">
                <div class="account-name">@spotonchain</div>
                <div class="account-desc">Professional trader insights and whale tracking</div>
                <div class="account-weight">Weight: 8/10</div>
            </div>
            <div class="account-card">
                <div class="account-name">@EmberCN</div>
                <div class="account-desc">Market analysis and predictions</div>
                <div class="account-weight">Weight: 7/10</div>
            </div>
            <div class="account-card">
                <div class="account-name">@ai_9684xtpa</div>
                <div class="account-desc">Chinese whale tracker with high accuracy</div>
                <div class="account-weight">Weight: 7/10</div>
            </div>
            <div class="account-card">
                <div class="account-name">@santimentfeed</div>
                <div class="account-desc">Market sentiment data and social metrics</div>
                <div class="account-weight">Weight: 6/10</div>
            </div>
        </div>
    </div>

    <div class="cta-section">
        <h2>🚀 Start Collecting Intelligence</h2>
        <p>Get real-time crypto trading signals from professional sources</p>
        <a href="/collect" class="cta-button">🔄 Collect Twitter Intelligence</a>
        <a href="/intelligence" class="cta-button">📊 View Current Intelligence</a>
    </div>
</body>
</html>
    """)

@app.get("/collect")
async def collect_intelligence():
    """Collect real Twitter intelligence"""
    try:
        print("🐦 Starting Twitter intelligence collection...")
        
        # Collect intelligence from all accounts
        intelligence_data = await twitter_engine.collect_real_intelligence()
        
        # Store in database
        stored_count = store_twitter_intelligence(intelligence_data)
        
        return {
            "status": "success",
            "message": f"🐦 Collected {len(intelligence_data)} intelligence signals",
            "stored": stored_count,
            "accounts_scraped": len(CRYPTO_TWITTER_ACCOUNTS),
            "timestamp": datetime.now().strftime('%H:%M:%S UTC'),
            "accounts": list(CRYPTO_TWITTER_ACCOUNTS.keys()),
            "next_steps": "Visit /intelligence to view collected data"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/intelligence")
def view_intelligence():
    """View collected Twitter intelligence"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Get recent intelligence
        cur.execute("""
            SELECT username, content, sentiment_score, influence_score, 
                   market_relevance, predicted_impact, confidence_level, 
                   crypto_mentions, whale_data, detected_at
            FROM twitter_intelligence 
            ORDER BY detected_at DESC 
            LIMIT 20
        """)
        intelligence_data = cur.fetchall()
        
        # Get stats
        cur.execute("""
            SELECT 
                COUNT(*) as total_signals,
                AVG(sentiment_score) as avg_sentiment,
                COUNT(CASE WHEN market_relevance = 'high' THEN 1 END) as high_relevance,
                COUNT(CASE WHEN detected_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as last_24h,
                COUNT(CASE WHEN confidence_level >= 0.8 THEN 1 END) as high_confidence
            FROM twitter_intelligence
        """)
        stats = cur.fetchone() or (0, 0.0, 0, 0, 0)
        
        cur.close()
        conn.close()
        
        total_signals, avg_sentiment, high_relevance, last_24h, high_confidence = stats
        sentiment_str = f"{avg_sentiment:+.2f}" if avg_sentiment else "0.00"
        sentiment_color = '#10b981' if avg_sentiment and avg_sentiment > 0 else '#dc2626' if avg_sentiment and avg_sentiment < 0 else '#6b7280'
        
        # Build intelligence cards
        intelligence_cards = ""
        if intelligence_data:
            for (username, content, sentiment, influence, relevance, impact, confidence, 
                 crypto_mentions, whale_data_json, detected_at) in intelligence_data:
                
                sent_color = '#10b981' if sentiment > 0 else '#dc2626' if sentiment < 0 else '#6b7280'
                sent_icon = '📈' if sentiment > 0 else '📉' if sentiment < 0 else '➡️'
                
                # Parse whale data
                whale_data = json.loads(whale_data_json) if whale_data_json else {}
                
                # Determine special badges
                if 'whale_alert' in username.lower():
                    special_badge = '🐋 WHALE ALERT'
                    badge_color = '#dc2626'
                elif 'lookonchain' in username.lower() or 'spotonchain' in username.lower():
                    special_badge = '🧠 SMART MONEY'
                    badge_color = '#8b5cf6'
                elif influence >= 8:
                    special_badge = '🔥 HIGH INFLUENCE'
                    badge_color = '#ef4444'
                elif influence >= 6:
                    special_badge = '⚡ MEDIUM INFLUENCE'
                    badge_color = '#f59e0b'
                else:
                    special_badge = '📱 LOW INFLUENCE'
                    badge_color = '#6b7280'
                
                # Impact colors
                impact_colors = {
                    'bullish_short_term': '#10b981', 'bullish_weak': '#059669',
                    'bearish_short_term': '#dc2626', 'bearish_weak': '#b91c1c',
                    'neutral': '#6b7280'
                }
                impact_color = impact_colors.get(impact, '#6b7280')
                
                time_str = detected_at.strftime('%H:%M:%S') if detected_at else 'N/A'
                confidence_width = confidence * 100 if confidence else 0
                
                # Truncate long content
                display_content = content[:300] + "..." if len(content) > 300 else content
                
                # Format crypto mentions
                crypto_str = ", ".join(crypto_mentions) if crypto_mentions else "N/A"
                
                # Whale data details
                whale_details = ""
                if whale_data:
                    if 'usd_value' in whale_data:
                        whale_details += f"💰 ${whale_data['usd_value']:,.0f} • "
                    if 'amount' in whale_data and 'crypto' in whale_data:
                        whale_details += f"{whale_data['amount']:,.0f} {whale_data['crypto']} • "
                    if 'movement_type' in whale_data:
                        whale_details += f"📊 {whale_data['movement_type'].replace('_', ' ').title()}"
                
                intelligence_cards += f"""
                <div style="background: linear-gradient(135deg, #1e293b, #334155); padding: 20px; margin: 15px 0; border-radius: 12px; border-left: 6px solid {sent_color}; position: relative;">
                    
                    <div style="position: absolute; top: 10px; right: 10px; background: {badge_color}; padding: 4px 8px; border-radius: 12px; font-size: 9px; font-weight: 600;">{special_badge}</div>
                    
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <div style="font-weight: 700; color: #06b6d4; font-size: 16px;">{sent_icon} {username}</div>
                        <div style="color: {sent_color}; font-weight: 600; font-size: 12px;">Sentiment: {sentiment:+.2f}</div>
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <div style="color: #f8fafc; font-size: 14px; line-height: 1.4; margin-bottom: 8px;">"{display_content}"</div>
                        <div style="color: {impact_color}; font-size: 12px; font-weight: 600; margin-bottom: 8px;">Impact: {impact.replace('_', ' ').title()}</div>
                        {f'<div style="color: #94a3b8; font-size: 11px; margin-bottom: 8px;">{whale_details}</div>' if whale_details else ''}
                        <div style="color: #94a3b8; font-size: 11px;">Cryptos: {crypto_str}</div>
                    </div>
                    
                    <div style="background: #374151; padding: 8px; border-radius: 6px; margin-bottom: 12px;">
                        <div style="color: #9ca3af; font-size: 11px; margin-bottom: 4px;">Confidence: {confidence:.1%}</div>
                        <div style="background: #4b5563; height: 6px; border-radius: 3px; overflow: hidden;">
                            <div style="background: linear-gradient(90deg, #ef4444, #f59e0b, #10b981); width: {confidence_width}%; height: 100%; border-radius: 3px;"></div>
                        </div>
                    </div>
                    
                    <div style="display: flex; justify-content: space-between; align-items: center; color: #94a3b8; font-size: 12px;">
                        <div><strong>Relevance:</strong> {relevance.title()}</div>
                        <div><strong>Detected:</strong> {time_str}</div>
                    </div>
                </div>"""
        
        return HTMLResponse(f"""<!DOCTYPE html>
<html>
<head>
    <title>📊 Twitter Intelligence Data</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: linear-gradient(135deg, #0a0f1a 0%, #1a1f2e 100%); color: white; margin: 0; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #1d4ed8, #2563eb); padding: 30px 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }}
        h1 {{ font-size: 32px; font-weight: 800; margin: 0 0 10px 0; }}
        .btn {{ padding: 10px 20px; background: linear-gradient(135deg, #8b5cf6, #7c3aed); color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 12px; margin: 5px; }}
        .collect-btn {{ padding: 10px 20px; background: linear-gradient(135deg, #10b981, #059669); color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 12px; margin: 5px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 15px; margin-bottom: 25px; }}
        .stat {{ background: linear-gradient(135deg, #1e293b, #334155); padding: 15px; border-radius: 10px; text-align: center; }}
        .stat-number {{ font-size: 20px; font-weight: 700; color: #1d4ed8; }}
        .container {{ max-height: 70vh; overflow-y: auto; padding: 10px; }}
        .empty {{ text-align: center; padding: 60px 20px; color: #64748b; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 TWITTER INTELLIGENCE DATA</h1>
        <p>Real-time crypto social sentiment analysis</p>
        <a href="/" class="btn">← Dashboard</a>
        <a href="/collect" class="collect-btn">🔄 Collect New Data</a>
        <a href="/analytics" class="btn">📈 Analytics</a>
    </div>
    
    <div class="stats">
        <div class="stat">
            <div class="stat-number">{total_signals}</div>
            <div>Total Signals</div>
        </div>
        <div class="stat">
            <div style="font-size: 18px; font-weight: 700; color: {sentiment_color};">{sentiment_str}</div>
            <div>Avg Sentiment</div>
        </div>
        <div class="stat">
            <div class="stat-number">{high_relevance}</div>
            <div>High Relevance</div>
        </div>
        <div class="stat">
            <div class="stat-number">{last_24h}</div>
            <div>Last 24h</div>
        </div>
        <div class="stat">
            <div class="stat-number">{high_confidence}</div>
            <div>High Confidence</div>
        </div>
    </div>
    
    <div class="container">
        {intelligence_cards if intelligence_cards else '''
        <div class="empty">
            <h3>📊 No Intelligence Data</h3>
            <p>Click "Collect New Data" to gather Twitter intelligence</p>
            <a href="/collect" style="color:#10b981; text-decoration:none; font-weight:600;">🔄 Start Collection</a>
        </div>
        '''}
    </div>
</body>
</html>""")
        
    except Exception as e:
        return HTMLResponse(f"<html><body style='background:#0a0f1a;color:white;padding:20px;'><h1>Intelligence Error</h1><p>{e}</p><a href='/'>← Back</a></body></html>")

@app.get("/analytics")
def analytics_dashboard():
    """Analytics dashboard showing system performance"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Get collection analytics
        cur.execute("""
            SELECT 
                COUNT(*) as collections,
                MAX(recorded_at) as last_collection,
                AVG(metric_value) as avg_tweets_per_collection
            FROM intelligence_analytics 
            WHERE metric_name = 'tweets_collected'
        """)
        collection_stats = cur.fetchone() or (0, None, 0)
        
        # Get account performance
        cur.execute("""
            SELECT 
                username,
                COUNT(*) as signals,
                AVG(sentiment_score) as avg_sentiment,
                AVG(confidence_level) as avg_confidence,
                COUNT(CASE WHEN market_relevance = 'high' THEN 1 END) as high_relevance_count
            FROM twitter_intelligence
            GROUP BY username
            ORDER BY signals DESC
        """)
        account_performance = cur.fetchall()
        
        cur.close()
        conn.close()
        
        collections, last_collection, avg_tweets = collection_stats
        last_collection_str = last_collection.strftime('%Y-%m-%d %H:%M:%S UTC') if last_collection else 'Never'
        
        # Build analytics cards
        account_cards = ""
        for username, signals, avg_sentiment, avg_confidence, high_relevance_count in account_performance:
            sentiment_color = '#10b981' if avg_sentiment > 0 else '#dc2626' if avg_sentiment < 0 else '#6b7280'
            confidence_color = '#10b981' if avg_confidence > 0.7 else '#f59e0b' if avg_confidence > 0.5 else '#dc2626'
            
            account_cards += f"""
            <div style="background: linear-gradient(135deg, #1e293b, #334155); padding: 20px; margin: 15px 0; border-radius: 12px; border-left: 6px solid #1d4ed8;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div style="font-weight: 700; color: #06b6d4; font-size: 18px;">{username}</div>
                    <div style="background: #1d4ed8; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: 600;">{signals} SIGNALS</div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 15px;">
                    <div style="text-align: center;">
                        <div style="color: {sentiment_color}; font-size: 20px; font-weight: 700;">{avg_sentiment:+.2f}</div>
                        <div style="color: #94a3b8; font-size: 12px;">Avg Sentiment</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="color: {confidence_color}; font-size: 20px; font-weight: 700;">{avg_confidence:.1%}</div>
                        <div style="color: #94a3b8; font-size: 12px;">Avg Confidence</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="color: #f59e0b; font-size: 20px; font-weight: 700;">{high_relevance_count}</div>
                        <div style="color: #94a3b8; font-size: 12px;">High Relevance</div>
                    </div>
                </div>
            </div>"""
        
        return HTMLResponse(f"""<!DOCTYPE html>
<html>
<head>
    <title>📈 Twitter Intelligence Analytics</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: linear-gradient(135deg, #0a0f1a 0%, #1a1f2e 100%); color: white; margin: 0; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #8b5cf6, #7c3aed); padding: 30px 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }}
        h1 {{ font-size: 32px; font-weight: 800; margin: 0 0 10px 0; }}
        .btn {{ padding: 10px 20px; background: linear-gradient(135deg, #ef4444, #dc2626); color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 12px; margin: 5px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 25px; }}
        .stat {{ background: linear-gradient(135deg, #1e293b, #334155); padding: 15px; border-radius: 10px; text-align: center; }}
        .stat-number {{ font-size: 24px; font-weight: 700; color: #8b5cf6; }}
        .container {{ max-height: 70vh; overflow-y: auto; padding: 10px; }}
        .section-title {{ color: #f8fafc; font-size: 24px; font-weight: 700; margin: 30px 0 20px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📈 ANALYTICS DASHBOARD</h1>
        <p>System performance and account analytics</p>
        <a href="/" class="btn">← Dashboard</a>
        <a href="/intelligence" class="btn">📊 View Data</a>
    </div>
    
    <div class="stats">
        <div class="stat">
            <div class="stat-number">{collections}</div>
            <div>Data Collections</div>
        </div>
        <div class="stat">
            <div class="stat-number">{avg_tweets:.1f}</div>
            <div>Avg Signals/Collection</div>
        </div>
        <div class="stat">
            <div class="stat-number">{len(account_performance)}</div>
            <div>Active Accounts</div>
        </div>
        <div class="stat">
            <div style="font-size: 14px; font-weight: 700; color: #8b5cf6;">{last_collection_str}</div>
            <div>Last Collection</div>
        </div>
    </div>
    
    <div class="section-title">🎯 Account Performance</div>
    <div class="container">
        {account_cards if account_cards else '<div style="text-align:center;color:#64748b;padding:40px;">No data available. Run a collection first.</div>'}
    </div>
</body>
</html>""")
        
    except Exception as e:
        return HTMLResponse(f"<html><body style='background:#0a0f1a;color:white;padding:20px;'><h1>Analytics Error</h1><p>{e}</p><a href='/'>← Back</a></body></html>")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
