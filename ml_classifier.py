"""
Night Watchman - ML-based Spam Classifier
Uses Ensemble Voting (Naive Bayes + Logistic Regression + Random Forest) for adaptive spam detection
"""

import os
import json
import logging
import re
from typing import Dict, Tuple, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Check if scikit-learn is available
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, VotingClassifier, GradientBoostingClassifier
    from sklearn.neural_network import MLPClassifier
    import pickle
    import numpy as np
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("scikit-learn not installed. ML classifier disabled.")

# Check if sentence-transformers is available
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Semantic analysis disabled.")


class SpamClassifier:
    """
    Machine Learning based spam classifier using Hybrid Approach.
    
    Modes:
    1. Standard: TF-IDF + Ensemble (NB, LR, RF)
    2. Advanced: Sentence Embeddings + Gradient Boosting + Manual Features
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        
        # Paths for standard model
        self.model_path = os.path.join(data_dir, "spam_model_v2.pkl")
        self.vectorizer_path = os.path.join(data_dir, "spam_vectorizer.pkl")
        
        # Paths for advanced model
        self.advanced_model_path = os.path.join(data_dir, "spam_model_advanced.pkl")
        
        self.dataset_path = os.path.join(data_dir, "spam_dataset.json")
        
        self.vectorizer = None
        self.model = None
        self.advanced_model = None
        self.embedding_model = None
        
        self.is_trained = False
        self.min_training_samples = 20
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Initialize Sentence Transformer if available
        if EMBEDDINGS_AVAILABLE:
            try:
                logger.info("⏳ Loading Sentence Transformer (this may take a moment)...")
                # 'all-MiniLM-L6-v2' is small (80MB) and fast
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("✅ Sentence Transformer loaded")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                # Don't modify global - just mark as unavailable for this instance
                self.embedding_model = None
        
        # Load or initialize dataset
        self.dataset = self._load_dataset()
        
        # Load or train models
        if ML_AVAILABLE:
            self._load_or_train_model()
    
    def _extract_manual_features(self, text: str) -> List[float]:
        """
        Extract heuristic features that often indicate spam.
        Returns a list of numerical features.
        """
        if not text:
            return [0.0] * 5
            
        text_len = len(text)
        caps_count = sum(1 for c in text if c.isupper())
        caps_ratio = caps_count / text_len if text_len > 0 else 0
        
        # Count links (URLs)
        link_count = len(re.findall(r'https?://|t\.me/', text.lower()))
        
        # Count emojis (simple regex approximation)
        # Ranges: Miscellaneous Symbols and Pictographs, Emoticons, Transport and Map Symbols
        emoji_count = len(re.findall(r'[\U0001F300-\U0001F6FF]', text))
        
        # Count "suspicious" characters (e.g. monetary symbols)
        money_count = len(re.findall(r'[\$\€\£]', text))
        
        # Feature vector: [length_norm, caps_ratio, link_count, emoji_count, money_count]
        # Normalize length (cap at 4096 chars)
        norm_len = min(text_len, 4096) / 4096.0
        
        return [norm_len, caps_ratio, float(link_count), float(emoji_count), float(money_count)]
    
    def _load_dataset(self) -> Dict:
        """Load training dataset from file."""
        if os.path.exists(self.dataset_path):
            try:
                with open(self.dataset_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading dataset: {e}")
        
        # Initialize with seed data
        return self._get_seed_dataset()
    
    def _get_seed_dataset(self) -> Dict:
        """Get initial seed dataset with known spam and ham examples."""
        return {
            "spam": [
                # Forex/Trading scams
                "Thanks to Kathy Lien my trading account is thriving with great returns",
                "From food stamps to $20,300 profit Mrs @forexqueen I bought my son a bike",
                "I use an automated trading system based on market conditions and advanced algorithms",
                "Send me a DM for more proof of my trading results",
                "My trading account grew from $500 to $50,000 in just 2 weeks",
                "Contact @tradingexpert for guaranteed daily returns of 5%",
                "Financial assistance without hassle, withdrawals are straightforward",
                "Thanks to this expert trader I made $10,000 in one week",
                "Join my trading team and earn $500-$1000 per week",
                "I was skeptical but now I make $200 daily from home",
                
                # Recruitment scams
                "New online project! Legal and secure activities on Bybit!",
                "Urgently seeking 2-3 individuals for remote employment",
                "70-80 dollars per day, only via phone or PC. Details in PM",
                "I am looking for 2-3 people to join my team at Bybit",
                "We're recruiting for a cool project, earn $500-$1000 per week",
                "Looking for partners for a completely remote project",
                "Earn from home, simple tasks, full training provided",
                "Write + if interested in earning extra income",
                "Opening recruitment for a new online opportunity",
                "Work from home and earn $1000+ weekly guaranteed",
                
                # Casino/Betting spam
                "Get your welcome bonus now at 1win casino",
                "Use promo code for free spins and $200 bonus",
                "I won $5000 on slots last night, try your luck",
                "Jackpot winner! Claim your bonus now",
                "Casino bonus activated on your balance",
                # 52casino specific (from real scam examples)
                "Congratulations! Your reward of $100 has been successfully received at 52casino",
                "Sign up here: www.52casino.cc and enter promo code lucky2026 for $100 bonus",
                "Dont forget: Enter promo code lucky2026 at signup to receive $100 instantly",
                "Story from 52 casino - Reward Received - $100 on your balance",
                "Check out 52casino and use code lucky2026 for free spins",
                "Your reward has been successfully received! Start playing today at 52casino",
                "Welcome bonus $200 at 52 casino, enter code to activate",
                
                # Generic scam patterns
                "DM me now for exclusive opportunity",
                "Inbox me for details on how to make money fast",
                "Click this link to claim your free crypto",
                "Guaranteed profit with no risk involved",
                "Send me $100 and I'll send back $1000",
                "Limited time offer, act now before it's too late",
                "I made $50,000 last month working from home",
                "This changed my life, you need to try this",
            ],
            "ham": [
                # Normal crypto discussion
                "What do you think about BTC price action today?",
                "I'm bullish on ETH for the long term",
                "Anyone using Mudrex for trading?",
                "The market is looking pretty volatile",
                "Should I DCA into Bitcoin or wait for a dip?",
                "What's the best strategy for beginners?",
                "I've been holding since 2020",
                "Is this a good entry point for SOL?",
                "The funding rates are really high right now",
                "Technical analysis shows support at 40k",
                
                # Normal questions
                "How do I withdraw my funds?",
                "What are the fees on this platform?",
                "Can someone help me with KYC verification?",
                "Is there a referral program?",
                "When will the new feature be released?",
                "I'm having trouble logging in",
                "How do I contact support?",
                "What's the minimum deposit amount?",
                "Can I use a credit card to buy crypto?",
                "How long does withdrawal take?",
                
                # Normal conversation
                "Good morning everyone!",
                "Thanks for the help",
                "That makes sense, appreciate it",
                "I agree with your analysis",
                "Interesting perspective",
                "Let's see how this plays out",
                "Happy trading everyone",
                "Stay safe out there",
                "Great community here",
                "Glad to be part of this group",
                
                # Mudrex specific
                "How does Mudrex work?",
                "What's the APY on the earn products?",
                "Is Mudrex available in my country?",
                "Can I use Mudrex on mobile?",
                "What coins can I trade on Mudrex?",
            ],
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    def _save_dataset(self):
        """Save dataset to file."""
        try:
            self.dataset["last_updated"] = datetime.now(timezone.utc).isoformat()
            with open(self.dataset_path, 'w', encoding='utf-8') as f:
                json.dump(self.dataset, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving dataset: {e}")
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for classification."""
        # Lowercase
        text = text.lower()
        # Remove URLs
        text = re.sub(r'https?://\S+|www\.\S+|t\.me/\S+', ' URL ', text)
        # Remove mentions but keep as token
        text = re.sub(r'@\w+', ' MENTION ', text)
        # Remove special characters but keep spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _load_or_train_model(self):
        """Load existing models or train new ones."""
        if not ML_AVAILABLE:
            return
        
        # 1. Try to load Standard Model
        standard_loaded = False
        if os.path.exists(self.model_path) and os.path.exists(self.vectorizer_path):
            try:
                with open(self.vectorizer_path, 'rb') as f:
                    self.vectorizer = pickle.load(f)
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                standard_loaded = True
                logger.info("📚 Standard ML model loaded")
            except Exception as e:
                logger.error(f"Error loading standard model: {e}")
        
        # 2. Try to load Advanced Model
        advanced_loaded = False
        if EMBEDDINGS_AVAILABLE and os.path.exists(self.advanced_model_path):
            try:
                with open(self.advanced_model_path, 'rb') as f:
                    self.advanced_model = pickle.load(f)
                advanced_loaded = True
                logger.info("🧠 Advanced AI model loaded")
            except Exception as e:
                logger.error(f"Error loading advanced model: {e}")
                
        self.is_trained = standard_loaded or advanced_loaded
        
        # Train if missing
        if not standard_loaded or (EMBEDDINGS_AVAILABLE and not advanced_loaded):
            self._train_models()
    
    def _train_models(self):
        """Train available models."""
        if not ML_AVAILABLE:
            return
        
        spam_samples = self.dataset.get("spam", [])
        ham_samples = self.dataset.get("ham", [])
        total_samples = len(spam_samples) + len(ham_samples)
        
        if total_samples < self.min_training_samples:
            logger.warning(f"Not enough training data ({total_samples}/{self.min_training_samples})")
            return

        # Prepare labels
        labels = [1] * len(spam_samples) + [0] * len(ham_samples)
        
        # --- Train Standard Model (TF-IDF) ---
        try:
            texts = [self._preprocess_text(t) for t in spam_samples + ham_samples]
            
            # Vectorizer
            self.vectorizer = TfidfVectorizer(
                max_features=2000,
                analyzer='char_wb',
                ngram_range=(3, 5),
                min_df=1
            )
            X = self.vectorizer.fit_transform(texts)
            
            # Ensemble
            self.model = VotingClassifier(
                estimators=[
                    ('naive_bayes', MultinomialNB(alpha=0.1)),
                    ('logistic_regression', LogisticRegression(max_iter=1000, random_state=42)),
                    ('random_forest', RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42))
                ],
                voting='soft'
            )
            self.model.fit(X, labels)
            
            # Save Standard
            with open(self.vectorizer_path, 'wb') as f:
                pickle.dump(self.vectorizer, f)
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            
            logger.info("✅ Standard model trained")
        except Exception as e:
            logger.error(f"Error training standard model: {e}")

        # --- Train Advanced Model (Embeddings + GradientBoosting) ---
        if EMBEDDINGS_AVAILABLE and self.embedding_model:
            try:
                raw_texts = spam_samples + ham_samples
                
                # 1. Generate Embeddings (Dense Vectors)
                embeddings = self.embedding_model.encode(raw_texts)
                
                # 2. Extract Manual Features
                manual_features = np.array([self._extract_manual_features(t) for t in raw_texts])
                
                # 3. Combine Features
                X_advanced = np.hstack((embeddings, manual_features))
                
                # 4. Train Gradient Boosting (Handle complex non-linear relationships)
                self.advanced_model = GradientBoostingClassifier(
                    n_estimators=100,
                    learning_rate=0.1,
                    max_depth=5,
                    random_state=42
                )
                self.advanced_model.fit(X_advanced, labels)
                
                # Save Advanced
                with open(self.advanced_model_path, 'wb') as f:
                    pickle.dump(self.advanced_model, f)
                    
                logger.info("🧠 Advanced AI model trained (Embeddings + Gradient Boosting)")
            except Exception as e:
                logger.error(f"Error training advanced model: {e}")

        self.is_trained = True

    def predict(self, text: str) -> Tuple[bool, float]:
        """
        Predict spam using the best available model.
        """
        if not ML_AVAILABLE or not self.is_trained:
            return False, 0.0
            
        # Try Advanced Model first
        if EMBEDDINGS_AVAILABLE and self.advanced_model and self.embedding_model:
            try:
                # Generate features
                emb = self.embedding_model.encode([text])
                manual = np.array([self._extract_manual_features(text)])
                X_input = np.hstack((emb, manual))
                
                # Predict
                probs = self.advanced_model.predict_proba(X_input)[0]
                is_spam = probs[1] > 0.5  # Threshold
                confidence = probs[1] if is_spam else probs[0]
                
                return bool(is_spam), float(confidence)
            except Exception as e:
                logger.error(f"Advanced prediction failed, falling back: {e}")
        
        # Fallback to Standard Model
        if self.model and self.vectorizer:
            try:
                processed = self._preprocess_text(text)
                X = self.vectorizer.transform([processed])
                probs = self.model.predict_proba(X)[0]
                is_spam = probs[1] > 0.5
                confidence = probs[1] if is_spam else probs[0]
                return bool(is_spam), float(confidence)
            except Exception as e:
                logger.error(f"Standard prediction failed: {e}")
                
        return False, 0.0

    def add_spam_sample(self, text: str):
        """Add a message to the spam training set."""
        if text and len(text) > 10:
            if text not in self.dataset["spam"]:
                self.dataset["spam"].append(text)
                self._save_dataset()
                logger.info(f"📝 Added spam sample (total: {len(self.dataset['spam'])})")
                
                # Retrain if we have enough new samples
                if len(self.dataset["spam"]) % 10 == 0:
                    self._train_model()
    
    def add_ham_sample(self, text: str):
        """Add a message to the ham (non-spam) training set."""
        if text and len(text) > 10:
            if text not in self.dataset["ham"]:
                self.dataset["ham"].append(text)
                self._save_dataset()
                logger.info(f"📝 Added ham sample (total: {len(self.dataset['ham'])})")
    
    def get_stats(self) -> Dict:
        """Get classifier statistics."""
        model_type = "Standard (Ensemble)"
        if self.advanced_model:
            model_type = "Hybrid (Ensemble + GradientBoosting/Embeddings)"
            
        return {
            "ml_available": ML_AVAILABLE,
            "embeddings_available": EMBEDDINGS_AVAILABLE,
            "is_trained": self.is_trained,
            "model_type": model_type if self.is_trained else "Not trained",
            "spam_samples": len(self.dataset.get("spam", [])),
            "ham_samples": len(self.dataset.get("ham", [])),
            "last_updated": self.dataset.get("last_updated", "never")
        }


# Global classifier instance
_classifier: Optional[SpamClassifier] = None


def get_classifier(data_dir: str = "data") -> SpamClassifier:
    """Get or create the global classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = SpamClassifier(data_dir)
    return _classifier
