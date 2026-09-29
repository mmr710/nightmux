import time
import random
import asyncio
import requests
from datetime import datetime
from twscrape import API, gather
from twitter.account import Account

import os
auth_token = os.environ.get("TWITTER_AUTH_TOKEN", "")

PROMO_TWEETS = [
    "Did you know you can run Claude Code on a remote server and control it completely from your phone via Telegram? 📱 That's exactly what Nightmux does. Check it out on GitHub! ⭐ https://github.com/mmr710/nightmux #ai #claudecode #agentic #vibecoding",
    "Managing multi-agent workflows is hard. Nightmux solves this by automatically tracking idle agents, handling API rate limits, and auto-resuming them if they crash. 🚀 https://github.com/mmr710/nightmux #ai #agentic #automation #claudecode",
    "Vibe coding from your couch just got a massive upgrade. You can spawn isolated Docker sandboxes and SSH drop-in to your agents with 1 click using Nightmux. 📦✨ https://github.com/mmr710/nightmux #vibecoding #ai #claudecode #agentic",
    "Ever had an AI agent destroy your repository with hallucinations? 😭 Nightmux adds an instant !rollback button that interrupts the agent and hard-resets the repo instantly. https://github.com/mmr710/nightmux #agentic #ai #vibecoding",
    "Stop pasting API keys into chats. 🛑 Nightmux has a secure Secrets Vault that silently injects encrypted keys directly into the agent's bash shell without logging them. https://github.com/mmr710/nightmux #ai #claudecode #security",
    "You can now run full Test-Driven Development loops with an AI agent autonomously. 🔄 Nightmux parses test outputs and forces the agent into a loop until tests pass. 🚀 https://github.com/mmr710/nightmux #agentic #ai #vibecoding",
    "Tired of opening your laptop to deploy? 💻 Nightmux lets you trigger production deployments directly from Telegram right after your AI agent finishes the feature. https://github.com/mmr710/nightmux #vibecoding #ai #agentic #claudecode",
    "Give your AI agents Native Web Browsing! 🌐 Nightmux allows agents to fetch full URLs, strip the HTML, and inject the markdown context directly into their workspace. https://github.com/mmr710/nightmux #ai #claudecode #agentic",
    "No more abandoned workflows. 🚨 Nightmux features a 20-minute Dead Man's Switch that pings you if your agent goes completely silent or gets stuck on a prompt. https://github.com/mmr710/nightmux #agentic #ai #automation #vibecoding",
    "Open-source AI orchestration is the future. If you are building with Claude or GPT, you need to be using Nightmux to manage your terminal sessions. Drop us a star! ⭐ https://github.com/mmr710/nightmux #ai #claudecode #vibecoding #agentic"
]

REPLY_MESSAGES = [
    "I just followed you! 🙌 I absolutely love connecting with fellow builders. I'd be so grateful if you could check out my open-source AI agent orchestrator, Nightmux, and drop it a GitHub star! ⭐ I'll star yours back! https://github.com/mmr710/nightmux #ai #agentic #vibecoding",
    "THIS IS AWESOME! 🔥 Just dropped you a follow! Let's support each other! 💪 Could you drop a star on our open-source AI dev tool? Drop your repo below and I'll star it back! ⭐ https://github.com/mmr710/nightmux #claudecode #ai #agentic",
    "WOOO! 🎉 You are absolutely crushing it! Just followed you to watch your journey! 🚀 If you have a second, I'd love a star on Nightmux! ⭐ Let me know what to support in return! https://github.com/mmr710/nightmux #vibecoding #claudecode",
    "LOVE THIS SO MUCH! 💖 Your perspective on AI is spot on! Followed! ✨ Drop a star on Nightmux if you want to support fellow open-source devs building agentic tools! https://github.com/mmr710/nightmux #ai #agentic #vibecoding",
    "WOW! 🤩 Just wanted to drop in and say you are doing an incredible job! Followed you! 🥂 Let's connect! Also, Nightmux would love a star if you have a moment! ⭐ https://github.com/mmr710/nightmux #claudecode #agentic",
    "SO TRUE! 🙌 Just hit that follow button! It's exciting to see the community tackle these problems! We're building Nightmux to make vibecoding easier! Help us reach 500 stars! 🚀 https://github.com/mmr710/nightmux #ai #vibecoding",
    "YOU NAILED IT! 🔨 Spot on analysis! Followed! ✨ If you want to manage AI agents like a boss, check out Nightmux and drop a star! Let's grow together! ⭐ https://github.com/mmr710/nightmux #agentic #claudecode",
    "100% THIS! 🔥 The AI space is better because of builders like you! Just followed! 🚀 Support our open-source Nightmux repo with a star? Let me know your project! https://github.com/mmr710/nightmux #ai #vibecoding #agentic"
]

def get_twitter_account():
    session = requests.Session()
    session.cookies.set("auth_token", auth_token, domain=".twitter.com")
    session.get("https://twitter.com")
    ct0 = session.cookies.get("ct0", domain=".twitter.com")
    if ct0:
        return Account(cookies={"auth_token": auth_token, "ct0": ct0})
    raise Exception("Could not fetch ct0")

async def get_search_results(query, limit=5):
    api = API()
    try:
        session = requests.Session()
        session.cookies.set("auth_token", auth_token, domain=".twitter.com")
        session.get("https://twitter.com")
        ct0 = session.cookies.get("ct0", domain=".twitter.com")
        await api.pool.add_account("nightmux_bot", os.environ.get("TWITTER_PASSWORD", ""), os.environ.get("TWITTER_EMAIL", ""), os.environ.get("TWITTER_EMAILPASS", ""), cookies=f"auth_token={auth_token}; ct0={ct0}")
    except Exception as e:
        pass
    
    try:
        await api.pool.login_all()
        # Fetch slightly more, we'll shuffle and slice later
        tweets = await gather(api.search(query, limit=limit))
        return tweets
    except Exception as e:
        print("Search error:", e)
        return []

def run_marketing_cycle():
    print(f"\n--- Starting stealth marketing cycle at {time.ctime()} ---")
    
    try:
        account = get_twitter_account()
        print("Logged in successfully.")
    except Exception as e:
        print("Login failed:", e)
        return

    # 1. Post a new tweet (75% chance so it's not strictly predictable)
    if random.random() < 0.75:
        try:
            tweet_text = random.choice(PROMO_TWEETS)
            
            # Attach interesting pictures about nightmux
            media_files = [
                "/home/ubuntu/nightmux/docs/hero.jpg",
                "/home/ubuntu/nightmux/docs/og.png"
            ]
            
            # 50% chance to include a picture with the promo tweet
            if random.random() < 0.5:
                chosen_image = random.choice(media_files)
                account.tweet(tweet_text, media=[{"media": chosen_image}])
                print(f"Posted new tweet with image {chosen_image}: {tweet_text}")
            else:
                account.tweet(tweet_text)
                print(f"Posted new tweet: {tweet_text}")
        except Exception as e:
            print("Error posting tweet:", e)
    else:
        print("Skipping posting a tweet this cycle to appear more human.")

    # Simulating human reading/scrolling delay
    sleep_time = random.randint(30, 180)
    print(f"Waiting {sleep_time} seconds before engaging...")
    time.sleep(sleep_time)

    # 2. Search and interact (like, reply, retweet)
    print("Searching for tweets to engage with...")
    # Added min_faves to ensure we only engage with tweets that have an active audience
    search_queries = [
        "#vibecoding min_faves:5", 
        "#claudecode min_faves:10", 
        "#agentic min_faves:5", 
        "build in public #ai", 
        "Claude AI developer",
        "AI workflow tools min_faves:10"
    ]
    
    # Get up to 15 tweets, interact with 5 to 10 to vastly increase daily growth volume
    tweets = asyncio.run(get_search_results(random.choice(search_queries), limit=15))
    random.shuffle(tweets)
    tweets_to_engage = tweets[:random.randint(5, 10)]
    
    for t in tweets_to_engage:
        print(f"\nEngaging with tweet {t.id} by {t.user.username}...")
        
        # Human delay before interaction
        time.sleep(random.randint(15, 60))
        
        # Determine if we will reply (50% chance for maximum growth)
        will_reply = random.random() < 0.5
        
        # ALWAYS Like if we are engaging
        try:
            account.like(t.id)
            print("  - Liked tweet")
        except Exception as e:
            print("  - Failed to like:", e)
        
        time.sleep(random.randint(5, 15))
            
        if will_reply:
            # If we reply saying "I just followed you", we MUST actually follow them
            try:
                account.follow(t.user.id)
                print(f"  - Followed user {t.user.username}")
            except Exception:
                try:
                    account.follow(t.user.username)
                    print(f"  - Followed user {t.user.username}")
                except Exception as e2:
                    print("  - Failed to follow:", e2)
                    
            time.sleep(random.randint(5, 15))
            
            try:
                reply_text = random.choice(REPLY_MESSAGES)
                account.reply(reply_text, tweet_id=t.id)
                print(f"  - Replied: {reply_text}")
            except Exception as e:
                print("  - Failed to reply:", e)
            
            time.sleep(random.randint(15, 45))
        
        # Retweet (15% chance to avoid spamming the timeline)
        if random.random() < 0.15:
            try:
                account.retweet(t.id)
                print("  - Retweeted")
            except Exception as e:
                print("  - Failed to retweet:", e)
                
        # Simulating time reading the next tweet
        time.sleep(random.randint(30, 90))
        
    print("--- Finished marketing cycle ---\n")

def main():
    print("Starting Highly-Optimized Nightmux Marketing Agent...")
    
    while True:
        run_marketing_cycle()
        
        # Run much more frequently: sleep a random amount between 1.5 and 4 hours (was 3.5 to 8)
        sleep_seconds = random.randint(int(1.5 * 3600), 4 * 3600)
        next_run = time.time() + sleep_seconds
        
        print(f"Sleeping for {sleep_seconds / 3600:.2f} hours. Next cycle at {time.ctime(next_run)}.")
        time.sleep(sleep_seconds)

if __name__ == '__main__':
    main()
