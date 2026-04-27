/**
 * Hungry Panda - Food Quotes Library
 * Quirky, engaging food quotes with panda flair for the ticker component
 * 
 * @module quotes
 * @version 1.0.0
 * @author Hungry Panda UX Team
 */

// ========================================
// ANALYSIS QUOTES - For AI analysis steps
// ========================================

/**
 * Quotes displayed during image/content analysis
 * Progressively revealed as AI processes the content
 */
export const ANALYSIS_QUOTES = [
  "🐼 Our AI panda is sniffing your delicious content...",
  "🎋 Analyzing pixels with bamboo-powered precision...",
  "🐼 Munching through visual data like fresh bamboo...",
  "🎋 Detecting flavors, colors, and culinary magic...",
  "🐼 Our panda chef is evaluating your masterpiece...",
  "🎋 Scanning for the perfect Instagram recipe...",
  "🐼 Crunching numbers with a side of bamboo...",
  "🎋 Identifying what makes this dish irresistible...",
  "🐼 The panda brain is processing your creation...",
  "🎋 Almost ready to serve some hot insights! 🔥"
];

// ========================================
// REEL QUOTES - For video/reel processing
// ========================================

/**
 * Quotes for video and reel generation steps
 * Matches the energy and pace of video content
 */
export const REEL_QUOTES = [
  "🐼 Rolling cameras! Panda director in action...",
  "🎬 Cutting scenes faster than bamboo grows...",
  "🐼 Our panda editor is working magic...",
  "🎬 Adding that cinematic bamboo flavor...",
  "🐼 Splicing moments into pure gold...",
  "🎬 Timing the perfect beat drop...",
  "🐼 This reel is going to be bamboo-tastic!",
  "🎬 Rendering with panda perfection...",
  "🐼 Almost ready for your viral moment...",
  "🎬 Action! Your reel masterpiece awaits! 🌟"
];

// ========================================
// GENERAL QUOTES - For loading states
// ========================================

/**
 * General food-related quotes for various loading states
 * Fun, engaging, full of personality
 */
export const GENERAL_QUOTES = [
  "🐼 Good things come to those who wait... and eat bamboo!",
  "🎋 Simmering ideas to perfection...",
  "🐼 Whisking up something delicious for your feed!",
  "🎋 Great content is like good soup—it takes time!",
  "🐼 Our pandas are working faster than takeout!",
  "🎋 Plating up your next viral moment...",
  "🐼 Turning your content into Instagram gold...",
  "🎋 Sprinkling some panda magic on your post...",
  "🐼 Hungry for success? We're cooking it up!",
  "🎋 Marinating your content in engagement sauce...",
  "🐼 This is going to be un-bamboo-lievable!",
  "🎋 Preheating the algorithm for maximum reach...",
  "🐼 Panda-approved content coming right up!",
  "🎋 Blending creativity with a dash of bamboo...",
  "🐼 Your post is getting the VIP treatment!",
  "🎋 Fermenting ideas into pure engagement...",
  "🐼 Slow-cooking perfection takes patience!",
  "🎋 Adding the secret ingredient: panda love!",
  "🐼 Sifting through possibilities like flour...",
  "🎋 Garnishing your content for maximum likes!",
  "🐼 Rising to the occasion like perfect dough...",
  "🎋 Steaming fresh content, panda-style!",
  "🐼 One bite of this content and you'll be hooked!",
  "🎋 Tossing ideas like a master chef!",
  "🐼 Your Instagram game is about to level up! 🚀",
  "🎋 Infusing every pixel with panda power...",
  "🐼 This content is worth the bamboo wait!",
  "🎋 Chopping, dicing, and optimizing...",
  "🐼 Serving looks hotter than spicy bamboo!",
  "🎋 The secret sauce? Pure panda dedication!"
];

// ========================================
// CATEGORY MAPPING
// ========================================

/**
 * All quote categories for easy access
 */
export const QUOTE_CATEGORIES = {
  ANALYSIS: 'analysis',
  REEL: 'reel',
  GENERAL: 'general'
};

/**
 * Map of categories to quote arrays
 */
const CATEGORY_MAP = {
  [QUOTE_CATEGORIES.ANALYSIS]: ANALYSIS_QUOTES,
  [QUOTE_CATEGORIES.REEL]: REEL_QUOTES,
  [QUOTE_CATEGORIES.GENERAL]: GENERAL_QUOTES
};

// ========================================
// UTILITY FUNCTIONS
// ========================================

/**
 * Gets a random quote from the specified category
 * 
 * @param {string} category - Category name ('analysis', 'reel', 'general')
 * @returns {string} Random quote from the category
 * @throws {Error} If category is invalid
 * 
 * @example
 * getRandomQuote('analysis') // "🐼 Our AI panda is sniffing your delicious content..."
 * getRandomQuote('general')  // "🐼 Good things come to those who wait..."
 */
export function getRandomQuote(category) {
  const normalizedCategory = category?.toLowerCase().trim();
  const quotes = CATEGORY_MAP[normalizedCategory];
  
  if (!quotes || quotes.length === 0) {
    console.warn(`Invalid quote category: ${category}. Falling back to general.`);
    return getRandomQuote(QUOTE_CATEGORIES.GENERAL);
  }
  
  const randomIndex = Math.floor(Math.random() * quotes.length);
  return quotes[randomIndex];
}

/**
 * Gets a quote for a specific analysis step
 * Provides progressive messaging as analysis completes
 * 
 * @param {number} stepIndex - Current step (0-9)
 * @returns {string} Quote appropriate for the current analysis step
 * 
 * @example
 * getAnalysisStep(0) // Starting analysis
 * getAnalysisStep(5) // Mid-analysis
 * getAnalysisStep(9) // Almost done
 */
export function getAnalysisStep(stepIndex) {
  const clampedIndex = Math.max(0, Math.min(stepIndex, ANALYSIS_QUOTES.length - 1));
  return ANALYSIS_QUOTES[clampedIndex];
}

/**
 * Gets a quote for a specific reel generation step
 * 
 * @param {number} stepIndex - Current step (0-9)
 * @returns {string} Quote appropriate for the current reel step
 */
export function getReelStep(stepIndex) {
  const clampedIndex = Math.max(0, Math.min(stepIndex, REEL_QUOTES.length - 1));
  return REEL_QUOTES[clampedIndex];
}

/**
 * Gets the progress percentage for an analysis step
 * 
 * @param {number} stepIndex - Current step (0-9)
 * @returns {number} Progress percentage (0-100)
 */
export function getAnalysisProgress(stepIndex) {
  const totalSteps = ANALYSIS_QUOTES.length;
  const clampedIndex = Math.max(0, Math.min(stepIndex, totalSteps - 1));
  return Math.round((clampedIndex / (totalSteps - 1)) * 100);
}

/**
 * Gets the progress percentage for a reel step
 * 
 * @param {number} stepIndex - Current step (0-9)
 * @returns {number} Progress percentage (0-100)
 */
export function getReelProgress(stepIndex) {
  const totalSteps = REEL_QUOTES.length;
  const clampedIndex = Math.max(0, Math.min(stepIndex, totalSteps - 1));
  return Math.round((clampedIndex / (totalSteps - 1)) * 100);
}

/**
 * Gets all quotes from a category
 * 
 * @param {string} category - Category name
 * @returns {string[]} Array of quotes
 */
export function getAllQuotes(category) {
  const normalizedCategory = category?.toLowerCase().trim();
  return [...(CATEGORY_MAP[normalizedCategory] || GENERAL_QUOTES)];
}

/**
 * Shuffles quotes array using Fisher-Yates algorithm
 * 
 * @param {string[]} quotes - Array of quotes to shuffle
 * @returns {string[]} New shuffled array
 */
export function shuffleQuotes(quotes) {
  const shuffled = [...quotes];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

/**
 * Gets a sequential quote iterator for a category
 * Cycles through quotes without repetition until all are shown
 * 
 * @param {string} category - Category name
 * @returns {object} Iterator object with next() method
 * 
 * @example
 * const iterator = getQuoteIterator('general');
 * console.log(iterator.next()); // First quote
 * console.log(iterator.next()); // Second quote
 */
export function getQuoteIterator(category) {
  const quotes = shuffleQuotes(getAllQuotes(category));
  let currentIndex = 0;
  
  return {
    next() {
      if (currentIndex >= quotes.length) {
        // Reshuffle when exhausted
        currentIndex = 0;
        quotes.length = 0;
        quotes.push(...shuffleQuotes(getAllQuotes(category)));
      }
      return quotes[currentIndex++];
    },
    reset() {
      currentIndex = 0;
      quotes.length = 0;
      quotes.push(...shuffleQuotes(getAllQuotes(category)));
    },
    get current() {
      return quotes[currentIndex] || quotes[0];
    }
  };
}

/**
 * Formats a quote with optional prefix/suffix
 * 
 * @param {string} quote - Original quote
 * @param {object} options - Formatting options
 * @returns {string} Formatted quote
 */
export function formatQuote(quote, options = {}) {
  const { prefix = '', suffix = '', uppercase = false } = options;
  let formatted = `${prefix}${quote}${suffix}`;
  
  if (uppercase) {
    formatted = formatted.toUpperCase();
  }
  
  return formatted;
}

/**
 * Search quotes by keyword
 * 
 * @param {string} keyword - Search term
 * @param {string} [category] - Optional category to search within
 * @returns {string[]} Matching quotes
 */
export function searchQuotes(keyword, category = null) {
  const searchTerm = keyword.toLowerCase();
  const quotesToSearch = category ? getAllQuotes(category) : [
    ...ANALYSIS_QUOTES,
    ...REEL_QUOTES,
    ...GENERAL_QUOTES
  ];
  
  return quotesToSearch.filter(quote => 
    quote.toLowerCase().includes(searchTerm)
  );
}

// ========================================
// SPECIALIZED QUOTE SETS
// ========================================

/**
 * Success celebration quotes
 */
export const SUCCESS_QUOTES = [
  "🐼 Bamboo-tastic! Your content is ready!",
  "🎋 Success tastes sweeter than fresh bamboo!",
  "🐼 Panda-approved and ready to shine!",
  "🎋 Your masterpiece is served! 🍽️",
  "🐼 Nailed it! Time to go viral!",
  "🎋 Chef's kiss! Perfect execution! 👨‍🍳"
];

/**
 * Error/recovery quotes
 */
export const ERROR_QUOTES = [
  "🐼 Oops! Our panda slipped on a bamboo stick...",
  "🎋 Don't worry, pandas always land on their feet!",
  "🐼 Let's try that again with more bamboo power!",
  "🎋 Even pandas make mistakes. Let's fix this!",
  "🐼 Hungry for success? We'll get there!"
];

/**
 * Get a success quote
 * @returns {string} Random success quote
 */
export function getSuccessQuote() {
  const randomIndex = Math.floor(Math.random() * SUCCESS_QUOTES.length);
  return SUCCESS_QUOTES[randomIndex];
}

/**
 * Get an error/recovery quote
 * @returns {string} Random error quote
 */
export function getErrorQuote() {
  const randomIndex = Math.floor(Math.random() * ERROR_QUOTES.length);
  return ERROR_QUOTES[randomIndex];
}

// ========================================
// DEFAULT EXPORT
// ========================================

export default {
  // Quote arrays
  ANALYSIS_QUOTES,
  REEL_QUOTES,
  GENERAL_QUOTES,
  SUCCESS_QUOTES,
  ERROR_QUOTES,
  
  // Constants
  QUOTE_CATEGORIES,
  
  // Functions
  getRandomQuote,
  getAnalysisStep,
  getReelStep,
  getAnalysisProgress,
  getReelProgress,
  getAllQuotes,
  shuffleQuotes,
  getQuoteIterator,
  formatQuote,
  searchQuotes,
  getSuccessQuote,
  getErrorQuote
};
