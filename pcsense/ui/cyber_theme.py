"""Cyberpunk/Glitch Theme Injector for Streamlit.

This module injects raw CSS into the Streamlit DOM to aggressively override 
the default styles with our High-Tech, Low-Life design system.
"""
import streamlit as st

def load_cyber_theme():
    cyber_css = """
    <style>
    /* 1. IMPORT FONTS */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap');

    /* 2. GLOBAL VARIABLES */
    :root {
        --color-bg: #0a0a0f;
        --color-fg: #e0e0e0;
        --color-card: #12121a;
        --color-muted: #1c1c2e;
        --color-accent: #00ff88;
        --color-accent-secondary: #ff00ff;
        --color-accent-tertiary: #00d4ff;
        --color-border: #2a2a3a;
        --color-destructive: #ff3366;
        
        --glow-neon: 0 0 5px #00ff88, 0 0 15px #00ff8840;
        --glow-neon-secondary: 0 0 5px #ff00ff, 0 0 15px #ff00ff60;
        --glow-neon-tertiary: 0 0 5px #00d4ff, 0 0 15px #00d4ff60;
        
        --clip-chamfer: polygon(0 10px, 10px 0, calc(100% - 10px) 0, 100% 10px, 100% calc(100% - 10px), calc(100% - 10px) 100%, 10px 100%, 0 calc(100% - 10px));
        --clip-chamfer-sm: polygon(0 6px, 6px 0, calc(100% - 6px) 0, 100% 6px, 100% calc(100% - 6px), calc(100% - 6px) 100%, 6px 100%, 0 calc(100% - 6px));
    }

    /* 3. GLOBAL TEXTURES (Scanlines & Circuit Grid) */
    .stApp {
        background-color: var(--color-bg);
        background-image: 
            linear-gradient(rgba(0, 255, 136, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 136, 0.03) 1px, transparent 1px);
        background-size: 40px 40px;
    }
    
    /* Scanline overlay */
    .stApp::after {
        content: "";
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background: repeating-linear-gradient(
            0deg,
            rgba(0, 0, 0, 0.15),
            rgba(0, 0, 0, 0.15) 1px,
            transparent 1px,
            transparent 2px
        );
        pointer-events: none;
        z-index: 999999;
    }

    /* 4. TYPOGRAPHY */
    html, body, [class*="css"] {
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
    }
    
    h1, h2, h3, .st-emotion-cache-10trblm {
        font-family: 'Orbitron', sans-serif !important;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    
    /* Main H1 Glitch Effect */
    h1 {
        color: var(--color-fg);
        text-shadow: 2px 0 var(--color-accent-secondary), -2px 0 var(--color-accent-tertiary);
        animation: glitch-anim 4s infinite linear alternate-reverse;
        position: relative;
    }

    @keyframes glitch-anim {
        0% { text-shadow: 2px 0 var(--color-accent-secondary), -2px 0 var(--color-accent-tertiary); }
        5% { text-shadow: -2px 0 var(--color-accent-secondary), 2px 0 var(--color-accent-tertiary); transform: skewX(2deg); }
        10% { text-shadow: 2px 0 var(--color-accent-secondary), -2px 0 var(--color-accent-tertiary); transform: skewX(0deg); }
        100% { text-shadow: 2px 0 var(--color-accent-secondary), -2px 0 var(--color-accent-tertiary); }
    }

    /* 5. COMPONENTS - BRUTALISM & GLOW */
    
    /* Buttons */
    div[data-testid="stButton"] > button {
        border-radius: 0 !important;
        background-color: transparent !important;
        border: 1px solid var(--color-accent) !important;
        color: var(--color-accent) !important;
        clip-path: var(--clip-chamfer-sm);
        font-family: 'Share Tech Mono', monospace !important;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        transition: all 150ms steps(4) !important;
        box-shadow: none !important;
    }
    div[data-testid="stButton"] > button:hover {
        background-color: var(--color-accent) !important;
        color: #000 !important;
        box-shadow: var(--glow-neon) !important;
        border-color: var(--color-accent) !important;
    }

    /* Specific overrides for Warning/Error buttons (we can't target specifically by text easily, 
       but we can let standard buttons shine). */
       
    /* Metrics / HUD Panels */
    [data-testid="stMetric"] {
        background-color: var(--color-card);
        border: 1px solid var(--color-border);
        border-left: 3px solid var(--color-accent-tertiary);
        padding: 1rem;
        clip-path: var(--clip-chamfer-sm);
    }
    [data-testid="stMetricValue"] {
        color: var(--color-accent) !important;
        font-family: 'Share Tech Mono', monospace !important;
        text-shadow: var(--glow-neon);
    }

    /* Inputs */
    .stTextInput > div > div > input {
        border-radius: 0 !important;
        background-color: var(--color-card) !important;
        border: 1px solid var(--color-border) !important;
        color: var(--color-accent) !important;
        clip-path: var(--clip-chamfer-sm);
    }
    .stTextInput > div > div:focus-within {
        border-color: var(--color-accent) !important;
        box-shadow: var(--glow-neon) !important;
    }

    /* Expanders / Cards */
    [data-testid="stExpander"] {
        background-color: var(--color-card);
        border: 1px solid var(--color-border) !important;
        border-radius: 0 !important;
        clip-path: var(--clip-chamfer-sm);
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        border-right: 1px solid var(--color-accent-secondary);
        background-color: var(--color-muted) !important;
    }
    
    /* Tabs */
    button[data-baseweb="tab"] {
        font-family: 'Share Tech Mono', monospace !important;
        text-transform: uppercase;
        border-radius: 0 !important;
    }
    
    /* Form wrapper for plan view */
    [data-testid="stForm"] {
        border: 1px solid var(--color-border);
        background: rgba(18, 18, 26, 0.7);
        border-left: 4px solid var(--color-accent-secondary);
        border-radius: 0;
        clip-path: var(--clip-chamfer);
    }
    </style>
    """
    st.markdown(cyber_css, unsafe_allow_html=True)
