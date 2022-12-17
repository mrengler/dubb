# token values for gpt3 context window
MAX_TOKENS_INPUT = 3000
MAX_TOKENS_OUTPUT = 1000
MAX_TOKENS_FACTS_QUOTES = 500
MAX_TOKENS_OUTPUT_BASE_MODEL = 4097
MAX_TOKENS_OUTPUT_IS_AD = 10
MAX_TOKENS_OUTPUT_IMAGE_DESCRIPTION = 120
MAX_TOKENS_OUTPUT_ARTICLE_FINAL = 2000

# rough approximation of string characters per token 
CHARS_PER_TOKEN = 3.55
# max number of facts
MAX_FACTS = 50
MAX_QUOTES = 5
MAX_KEYWORDS = 10

# OpenAI toxic threshold
# This is the probability at which we evaluate that a "2" is likely real
# vs. should be discarded as a false positive
TOXIC_THRESHOLD = -0.355

# max audio and video clips to produce
NUM_AUDIOS_TO_PRODUCE = 5
NUM_VIDEOS_TO_PRODUCE = 3

# constants for video creation
DOUBLE = 2
FRAME_RATE = 10
MIN_VIDEO_LENGTH = 20
