import os
import json
import psycopg2
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
import re
import hashlib

# STANDALONE TWITTER INTELLIGENCE DATABASE
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://username:password@host:5432/database_name")

app = FastAPI(title="Edgedar Twitter Intelligence")

def create_database_tables():
    """Create database tables for Twitter intelligence"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
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
                detected_at TIMESTAMP DEFAULT NOW()
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

def generate_sample_intelligence():
    """Generate sample Twitter intelligence data"""
    current_time = datetime.now()
    
    sample_data = [
        {
            'content': '🚨 15,000 #ETH (36,852,000 USD) transferred from unknown wallet to #Binance',
            'username': '@whale_alert',
            'sentiment': -0.3,
            'influence': 9,
            'relevance': 'high',
            'impact': 'bearish_short_term',
            'confidence': 0.85
        },
        {
            'content': 'Smart money wallet bought 2,500 ETH after the dip. This address has 78% win rate.',
            'username': '@lookonchain',
            'sentiment': 0.7,
            'influence': 8,
            'relevance': 'high',
            'impact': 'bullish_short_term',
            'confidence': 0.78
        },
        {
            'content': 'Bitcoin forming bull flag pattern on 4H chart. Target $72,000 if it breaks $68,500.',
            'username': '@EmberCN',
            'sentiment': 0.6,
            'influence': 7,
            'relevance': 'medium',
            'impact': 'bullish_medium_term',
            'confidence': 0.72
        },
        {
            'content': '850 #BTC (57,630,000 USD) transferred from #Coinbase to unknown wallet',
            'username': '@whale_alert',
            'sentiment': 0.4,
            'influence': 9,
            'relevance': 'high',
            'impact': 'bullish_short_term',
            'confidence': 0.88
        },
        {
            'content': 'Social sentiment for $BTC hits 3-week high. Often precedes 5-8% moves within 72h.',
            'username': '@santimentfeed',
            'sentiment': 0.4,
            'influence': 6,
            'relevance': 'medium',
            'impact': 'bullish_weak',
            'confidence': 0.65
        }
    ]
    
    return sample_data

def store_intelligence_data(data_list):
    """Store intelligence data in database"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Clear old data
        cur.execute("DELETE FROM twitter_intelligence WHERE detected_at < NOW() - INTERVAL '24 hours'")
        
        stored_count = 0
        for item in data_list:
            tweet_id = hashlib.md5(f"{item['username']}_{item['content'][:50]}_{datetime.now()}".encode()).hexdigest()
            
            try:
                cur.execute("""
                    INSERT INTO twitter_intelligence (
                        tweet_id, username, content, sentiment_score, influence_score,
                        market_relevance, predicted_impact, confidence_level, detected_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (tweet_id) DO NOTHING
                """, (
                    tweet_id, item['username'], item['content'], item['sentiment'],
                    item['influence'], item['relevance'], item['impact'], item['confidence']
                ))
                stored_count += 1
            except Exception as e:
                print(f"Error storing item: {e}")
                continue
        
        conn.commit()
        cur.close()
        conn.close()
        return stored_count
        
    except Exception as e:
        print(f"Error storing data: {e}")
        return 0

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
    <title>🐦 Twitter Intelligence</title>
    <style>
        body { font-family: Arial, sans-serif; background: #0a0f1a; color: white; margin: 0; padding: 20px; }
        .header { background: linear-gradient(135deg, #1d4ed8, #2563eb); padding: 30px; border-radius: 15px; text-align: center; margin-bottom: 30px; }
        h1 { font-size: 36px; margin: 0 0 10px 0; }
        .nav { text-align: center; margin: 20px 0; }
        .btn { display: inline-block; padding: 12px 24px; background: #10b981; color: white; text-decoration: none; border-radius: 8px; margin: 5px; font-weight: bold; }
        .btn:hover { background: #059669; }
        .status { background: #1e293b; padding: 20px; border-radius: 10px; text-align: center; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐦 TWITTER INTELLIGENCE</h1>
        <p>Real-time crypto social sentiment analysis</p>
    </div>
    
    <div class="nav">
        <a href="/" class="btn">🏠 Dashboard</a>
        <a href="/collect" class="btn">🔄 Collect Data</a>
        <a href="/intelligence" class="btn">📊 View Intelligence</a>
        <a href="https://edgedar-scraper-v2.onrender.com" class="btn" target="_blank">← Main Dashboard</a>
    </div>
    
    <div class="status">
        <h2>🚀 System Ready</h2>
        <p>Twitter Intelligence monitoring system operational</p>
        <p>Click "Collect Data" to generate intelligence signals</p>
    </div>
</body>
</html>
    """)

@app.get("/collect")
def collect_intelligence():
    """Collect Twitter intelligence data"""
    try:
        data = generate_sample_intelligence()
        stored = store_intelligence_data(data)
        
        return {
            "status": "success",
            "message": f"🐦 Collected {len(data)} intelligence signals",
            "stored": stored,
            "timestamp": datetime.now().strftime('%H:%M:%S UTC')
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/intelligence")
def view_intelligence():
    """View Twitter intelligence data"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT username, content, sentiment_score, influence_score,
                   market_relevance, predicted_impact, confidence_level, detected_at
            FROM twitter_intelligence 
            ORDER BY detected_at DESC 
            LIMIT 10
        """)
        data = cur.fetchall()
        
        cur.execute("SELECT COUNT(*) FROM twitter_intelligence")
        total_count = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        cards = ""
        if data:
            for (username, content, sentiment, influence, relevance, impact, confidence, detected) in data:
                sent_color = '#10b981' if sentiment > 0 else '#dc2626' if sentiment < 0 else '#6b7280'
                sent_icon = '📈' if sentiment > 0 else '📉' if sentiment < 0 else '➡️'
                
                time_str = detected.strftime('%H:%M:%S') if detected else 'N/A'
                confidence_width = confidence * 100 if confidence else 0
                
                cards += f"""
                <div style="background: #1e293b; padding: 20px; margin: 15px 0; border-radius: 10px; border-left: 6px solid {sent_color};">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                        <strong style="color: #06b6d4;">{sent_icon} {username}</strong>
                        <span style="color: {sent_color};">Sentiment: {sentiment:+.2f}</span>
                    </div>
                    <p style="color: #f8fafc; margin: 10px 0;">"{content}"</p>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin: 10px 0; font-size: 12px; color: #94a3b8;">
                        <div>Impact: {impact.replace('_', ' ').title()}</div>
                        <div>Relevance: {relevance.title()}</div>
                        <div>Time: {time_str}</div>
                    </div>
                    <div style="background: #374151; padding: 5px; border-radius: 5px;">
                        <div style="font-size: 11px; color: #9ca3af;">Confidence: {confidence:.1%}</div>
                        <div style="background: #4b5563; height: 4px; border-radius: 2px;">
                            <div style="background: #10b981; width: {confidence_width}%; height: 100%; border-radius: 2px;"></div>
                        </div>
                    </div>
                </div>"""
        
        return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
    <title>📊 Intelligence Data</title>
    <style>
        body {{ font-family: Arial, sans-serif; background: #0a0f1a; color: white; margin: 0; padding: 20px; }}
        .header {{ background: #1d4ed8; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px; }}
        .btn {{ display: inline-block; padding: 10px 20px; background: #10b981; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
        .stats {{ background: #1e293b; padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 INTELLIGENCE DATA</h1>
        <a href="/" class="btn">← Dashboard</a>
        <a href="/collect" class="btn">🔄 Collect New Data</a>
    </div>
    
    <div class="stats">
        <strong>Total Signals: {total_count}</strong>
    </div>
    
    <div>
        {cards if cards else '<div style="text-align: center; padding: 40px; color: #64748b;"><h3>No Data</h3><p><a href="/collect" style="color:#10b981;">Collect data first</a></p></div>'}
    </div>
</body>
</html>""")
        
    except Exception as e:
        return HTMLResponse(f"<html><body style='background:#0a0f1a;color:white;padding:20px;'><h1>Error</h1><p>{e}</p><a href='/'>← Back</a></body></html>")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
