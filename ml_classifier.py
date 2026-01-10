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
    from sklearn.ensemble import RandomForestClassifier, VotingClassifier
    import pickle
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("scikit-learn not installed. ML classifier disabled.")


class SpamClassifier:
    """
    Machine Learning based spam classifier using Ensemble Voting.
    Combines Naive Bayes, Logistic Regression, and Random Forest for robust detection.
    Learns from training data and admin actions.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.model_path = os.path.join(data_dir, "spam_model_v2.pkl")
        self.vectorizer_path = os.path.join(data_dir, "spam_vectorizer.pkl")
        self.dataset_path = os.path.join(data_dir, "spam_dataset.json")
        
        self.vectorizer = None
        self.model = None
        self.is_trained = False
        self.min_training_samples = 20  # Minimum samples needed to train
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Load or initialize dataset
        self.dataset = self._load_dataset()
        
        # Load or train model
        if ML_AVAILABLE:
            self._load_or_train_model()
    
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
        """Load existing model or train a new one."""
        if not ML_AVAILABLE:
            return
        
        # Try to load existing model and vectorizer
        if os.path.exists(self.model_path) and os.path.exists(self.vectorizer_path):
            try:
                with open(self.vectorizer_path, 'rb') as f:
                    self.vectorizer = pickle.load(f)
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                self.is_trained = True
                logger.info("📚 ML ensemble model loaded from file")
                return
            except Exception as e:
                logger.error(f"Error loading model: {e}")
        
        # Train new model
        self._train_model()
    
    def _train_model(self):
        """Train the ensemble spam classifier."""
        if not ML_AVAILABLE:
            return
        
        spam_samples = self.dataset.get("spam", [])
        ham_samples = self.dataset.get("ham", [])
        
        total_samples = len(spam_samples) + len(ham_samples)
        
        if total_samples < self.min_training_samples:
            logger.warning(f"Not enough training data ({total_samples}/{self.min_training_samples})")
            return
        
        # Prepare training data
        texts = []
        labels = []
        
        for text in spam_samples:
            texts.append(self._preprocess_text(text))
            labels.append(1)  # 1 = spam
        
        for text in ham_samples:
            texts.append(self._preprocess_text(text))
            labels.append(0)  # 0 = ham (not spam)
        
        try:
            # Create TF-IDF vectorizer
            self.vectorizer = TfidfVectorizer(
                max_features=1500,
                ngram_range=(1, 2),  # Use unigrams and bigrams
                min_df=1,
                stop_words='english'
            )
            
            # Transform texts to features
            X = self.vectorizer.fit_transform(texts)
            
            # Create ensemble with 3 classifiers
            nb_clf = MultinomialNB(alpha=0.1)
            lr_clf = LogisticRegression(max_iter=1000, random_state=42)
            rf_clf = RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42)
            
            # Voting classifier - soft voting uses predicted probabilities
            self.model = VotingClassifier(
                estimators=[
                    ('naive_bayes', nb_clf),
                    ('logistic_regression', lr_clf),
                    ('random_forest', rf_clf)
                ],
                voting='soft'  # Use probability-based voting
            )
            
            self.model.fit(X, labels)
            self.is_trained = True
            
            # Save model and vectorizer
            with open(self.vectorizer_path, 'wb') as f:
                pickle.dump(self.vectorizer, f)
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            
            logger.info(f"🤖 ML ensemble model trained: {len(spam_samples)} spam + {len(ham_samples)} ham samples (3 classifiers)")
        except Exception as e:
            logger.error(f"Error training model: {e}")
            self.is_trained = False
    
    def predict(self, text: str) -> Tuple[bool, float]:
        """
        Predict if a message is spam using ensemble voting.
        
        Returns:
            Tuple of (is_spam: bool, confidence: float)
        """
        if not ML_AVAILABLE or not self.is_trained or not self.model or not self.vectorizer:
            return False, 0.0
        
        try:
            processed = self._preprocess_text(text)
            
            # Transform text using vectorizer
            X = self.vectorizer.transform([processed])
            
            # Get prediction and probability from ensemble
            prediction = self.model.predict(X)[0]
            probabilities = self.model.predict_proba(X)[0]
            
            is_spam = prediction == 1
            confidence = probabilities[1] if is_spam else probabilities[0]
            
            return is_spam, float(confidence)
        except Exception as e:
            logger.error(f"Error predicting: {e}")
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
        return {
            "ml_available": ML_AVAILABLE,
            "is_trained": self.is_trained,
            "model_type": "Ensemble (NB + LR + RF)" if self.is_trained else "Not trained",
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
