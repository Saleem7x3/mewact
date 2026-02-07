try:
    from ollama import Client
    print('Success')
except ImportError:
    print('Failure')
