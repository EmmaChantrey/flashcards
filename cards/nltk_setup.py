import nltk

# downloads nltk packages if not already downloaded
def initialize_nltk():
    required_nltk_packages = [
        'punkt',
        'wordnet',
        'omw-1.4',
        'stopwords'
    ]
    
    for package in required_nltk_packages:
        try:
            nltk.data.find(f'tokenizers/{package}')
        except LookupError:
            nltk.download(package)