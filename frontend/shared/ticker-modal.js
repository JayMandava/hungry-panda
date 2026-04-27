/**
 * Hungry Panda - Thinking Process Ticker Modal
 * Reusable modal component for showing AI processing with engaging content
 *
 * Features:
 * - Full-screen glassmorphism overlay
 * - Animated panda mascot with progress ring
 * - Scrolling ticker tape with rotating quotes
 * - Step indicator and time estimation
 * - Cannot dismiss by clicking outside (processing must complete)
 * - Cancel button for user abort
 * - Reduced motion support
 * - Full accessibility (aria-live, role="dialog")
 *
 * @module ticker-modal
 * @version 1.0.0
 * @author Hungry Panda UX Team
 */

import {
  getAnalysisStep,
  getReelStep,
  getRandomQuote,
  QUOTE_CATEGORIES
} from './quotes.js';

import {
  animate,
  EASING_SPRING,
  EASING_SMOOTH,
  EASING_DRAMATIC,
  DURATION_BASE,
  DURATION_SLOW,
  DURATION_DRAMATIC,
  prefersReducedMotion
} from './animations.js';

// ========================================
// CONSTANTS
// ========================================

const MODAL_TYPES = {
  ANALYSIS: 'analysis',
  REEL: 'reel'
};

const DEFAULT_STEPS = {
  [MODAL_TYPES.ANALYSIS]: [
    'Uploading...',
    'Analyzing composition...',
    'Detecting food type...',
    'Identifying ingredients...',
    'Evaluating presentation...',
    'Generating caption...',
    'Optimizing hashtags...',
    'Finalizing...'
  ],
  [MODAL_TYPES.REEL]: [
    'Preparing media...',
    'Processing video...',
    'Generating scenes...',
    'Adding transitions...',
    'Syncing audio...',
    'Applying effects...',
    'Rendering reel...',
    'Finalizing...'
  ]
};

const DEFAULT_OPTIONS = {
  type: MODAL_TYPES.ANALYSIS,
  title: 'Processing...',
  showCancel: true,
  cancelText: 'Cancel',
  estimatedTime: null,
  onCancel: null,
  onComplete: null
};

const STYLES = {
  overlay: `
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    opacity: 0;
    transition: opacity 250ms ease;
  `,
  modal: `
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.85) 0%, rgba(255, 255, 255, 0.75) 100%);
    backdrop-filter: blur(40px) saturate(180%);
    -webkit-backdrop-filter: blur(40px) saturate(180%);
    border: 2px solid rgba(255, 255, 255, 0.5);
    border-radius: 24px;
    box-shadow: 0 8px 32px rgba(110, 154, 66, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.8);
    max-width: 600px;
    width: calc(100% - 32px);
    margin: 16px;
    padding: 40px 32px;
    text-align: center;
    opacity: 0;
    transform: scale(0.9);
    position: relative;
    overflow: hidden;
  `,
  pandaContainer: `
    position: relative;
    width: 120px;
    height: 120px;
    margin: 0 auto 24px;
  `,
  pandaEmoji: `
    font-size: 64px;
    line-height: 1;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 2;
  `,
  progressRing: `
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
    z-index: 1;
  `,
  progressCircle: `
    fill: none;
    stroke-width: 4;
  `,
  progressBg: `
    stroke: rgba(110, 154, 66, 0.15);
  `,
  progressFg: `
    stroke: #6e9a42;
    stroke-linecap: round;
    stroke-dasharray: 339.292;
    stroke-dashoffset: 339.292;
    transition: stroke-dashoffset 300ms ease;
  `,
  title: `
    font-size: 24px;
    font-weight: 600;
    color: #1a1a1a;
    margin: 0 0 8px;
    font-family: inherit;
  `,
  currentOperation: `
    font-size: 16px;
    color: #6e9a42;
    margin: 0 0 16px;
    font-weight: 500;
    min-height: 24px;
  `,
  tickerContainer: `
    background: linear-gradient(135deg, rgba(110, 154, 66, 0.08) 0%, rgba(110, 154, 66, 0.04) 100%);
    border-radius: 12px;
    padding: 16px 20px;
    margin: 0 0 20px;
    border: 1px solid rgba(110, 154, 66, 0.15);
    overflow: hidden;
    position: relative;
  `,
  tickerText: `
    font-size: 14px;
    color: #4a4a4a;
    font-style: italic;
    margin: 0;
    line-height: 1.5;
    min-height: 21px;
  `,
  stepIndicator: `
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin: 0 0 16px;
  `,
  stepDot: `
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgba(110, 154, 66, 0.2);
    transition: all 300ms ease;
  `,
  stepDotActive: `
    background: #6e9a42;
    transform: scale(1.3);
  `,
  stepDotCompleted: `
    background: #6e9a42;
  `,
  timeEstimate: `
    font-size: 13px;
    color: #888;
    margin: 0 0 24px;
  `,
  cancelButton: `
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 500;
    color: #666;
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 8px;
    cursor: pointer;
    transition: all 150ms ease;
  `,
  cancelButtonHover: `
    background: rgba(255, 255, 255, 0.9);
    border-color: rgba(0, 0, 0, 0.15);
    transform: translateY(-1px);
  `,
  cancelButtonActive: `
    transform: scale(0.98);
  `,
  glowEffect: `
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle at center, rgba(110, 154, 66, 0.1) 0%, transparent 60%);
    pointer-events: none;
    z-index: 0;
  `
};

// ========================================
// TickerModal Class
// ========================================

class TickerModal {
  constructor() {
    this.overlay = null;
    this.modal = null;
    this.isOpen = false;
    this.currentType = MODAL_TYPES.ANALYSIS;
    this.currentStep = 0;
    this.totalSteps = 8;
    this.progress = 0;
    this.quoteInterval = null;
    this.typewriterInterval = null;
    this.cancelCallback = null;
    this.steps = [];
    this.currentQuote = '';
    this.quoteIterator = null;
    this.startTime = null;
    this.estimatedDuration = null;
    
    // Bind methods
    this.handleCancel = this.handleCancel.bind(this);
    this.handleKeydown = this.handleKeydown.bind(this);
    this.updateQuote = this.updateQuote.bind(this);
  }

  /**
   * Creates the modal DOM structure
   * @private
   */
  createModal() {
    // Create overlay
    this.overlay = document.createElement('div');
    this.overlay.className = 'ticker-modal-overlay';
    this.overlay.setAttribute('role', 'dialog');
    this.overlay.setAttribute('aria-modal', 'true');
    this.overlay.setAttribute('aria-live', 'polite');
    this.overlay.style.cssText = STYLES.overlay;

    // Create modal card
    this.modal = document.createElement('div');
    this.modal.className = 'ticker-modal-card';
    this.modal.style.cssText = STYLES.modal;

    // Add glow effect
    const glow = document.createElement('div');
    glow.style.cssText = STYLES.glowEffect;
    this.modal.appendChild(glow);

    // Create panda container with progress ring
    const pandaContainer = document.createElement('div');
    pandaContainer.className = 'ticker-panda-container';
    pandaContainer.style.cssText = STYLES.pandaContainer;

    // Progress ring SVG
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'ticker-progress-ring');
    svg.setAttribute('width', '120');
    svg.setAttribute('height', '120');
    svg.style.cssText = STYLES.progressRing;

    // Background circle
    const bgCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    bgCircle.setAttribute('cx', '60');
    bgCircle.setAttribute('cy', '60');
    bgCircle.setAttribute('r', '54');
    bgCircle.style.cssText = STYLES.progressCircle + STYLES.progressBg;
    svg.appendChild(bgCircle);

    // Progress circle
    this.progressCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    this.progressCircle.setAttribute('cx', '60');
    this.progressCircle.setAttribute('cy', '60');
    this.progressCircle.setAttribute('r', '54');
    this.progressCircle.style.cssText = STYLES.progressCircle + STYLES.progressFg;
    svg.appendChild(this.progressCircle);

    pandaContainer.appendChild(svg);

    // Panda emoji
    this.pandaEmoji = document.createElement('div');
    this.pandaEmoji.className = 'ticker-panda-emoji';
    this.pandaEmoji.textContent = '🐼';
    this.pandaEmoji.style.cssText = STYLES.pandaEmoji;
    this.pandaEmoji.setAttribute('aria-hidden', 'true');
    pandaContainer.appendChild(this.pandaEmoji);

    this.modal.appendChild(pandaContainer);

    // Title
    this.titleElement = document.createElement('h2');
    this.titleElement.className = 'ticker-title';
    this.titleElement.style.cssText = STYLES.title;
    this.modal.appendChild(this.titleElement);

    // Current operation
    this.operationElement = document.createElement('p');
    this.operationElement.className = 'ticker-operation';
    this.operationElement.style.cssText = STYLES.currentOperation;
    this.modal.appendChild(this.operationElement);

    // Ticker container
    const tickerContainer = document.createElement('div');
    tickerContainer.className = 'ticker-quote-container';
    tickerContainer.style.cssText = STYLES.tickerContainer;

    // Ticker text
    this.quoteElement = document.createElement('p');
    this.quoteElement.className = 'ticker-quote-text';
    this.quoteElement.style.cssText = STYLES.tickerText;
    tickerContainer.appendChild(this.quoteElement);

    this.modal.appendChild(tickerContainer);

    // Step indicator
    this.stepIndicator = document.createElement('div');
    this.stepIndicator.className = 'ticker-step-indicator';
    this.stepIndicator.style.cssText = STYLES.stepIndicator;
    this.modal.appendChild(this.stepIndicator);

    // Time estimate
    this.timeElement = document.createElement('p');
    this.timeElement.className = 'ticker-time-estimate';
    this.timeElement.style.cssText = STYLES.timeEstimate;
    this.modal.appendChild(this.timeElement);

    // Cancel button
    this.cancelButton = document.createElement('button');
    this.cancelButton.className = 'ticker-cancel-button';
    this.cancelButton.style.cssText = STYLES.cancelButton;
    this.cancelButton.type = 'button';
    this.cancelButton.addEventListener('click', this.handleCancel);
    this.cancelButton.addEventListener('mouseenter', () => {
      this.cancelButton.style.cssText = STYLES.cancelButton + STYLES.cancelButtonHover;
    });
    this.cancelButton.addEventListener('mouseleave', () => {
      this.cancelButton.style.cssText = STYLES.cancelButton;
    });
    this.cancelButton.addEventListener('mousedown', () => {
      this.cancelButton.style.cssText = STYLES.cancelButton + STYLES.cancelButtonActive;
    });
    this.cancelButton.addEventListener('mouseup', () => {
      this.cancelButton.style.cssText = STYLES.cancelButton + STYLES.cancelButtonHover;
    });
    this.modal.appendChild(this.cancelButton);

    // Assemble modal
    this.overlay.appendChild(this.modal);

    // Prevent clicking outside to close
    this.overlay.addEventListener('click', (e) => {
      if (e.target === this.overlay) {
        // Visual feedback that modal cannot be dismissed
        this.shakeModal();
      }
    });

    return this;
  }

  /**
   * Shows the ticker modal with the specified options
   * @param {object} options - Configuration options
   * @param {string} options.type - 'analysis' or 'reel'
   * @param {string} options.title - Modal title
   * @param {boolean} options.showCancel - Whether to show cancel button
   * @param {string} options.cancelText - Cancel button text
   * @param {number} options.estimatedTime - Estimated time in seconds
   * @param {function} options.onCancel - Cancel callback
   * @param {function} options.onComplete - Complete callback
   * @returns {TickerModal} this instance for chaining
   * 
   * @example
   * tickerModal.showTicker({
   *   type: 'analysis',
   *   title: 'Analyzing your food photo...',
   *   estimatedTime: 30,
   *   onCancel: () => console.log('User cancelled')
   * });
   */
  showTicker(options = {}) {
    console.log('[TickerModal] showTicker called with options:', options);

    if (this.isOpen) {
      console.warn('[TickerModal] Already open, returning');
      return this;
    }

    const config = { ...DEFAULT_OPTIONS, ...options };
    console.log('[TickerModal] Config:', config);
    this.currentType = config.type;
    this.steps = DEFAULT_STEPS[config.type] || DEFAULT_STEPS[MODAL_TYPES.ANALYSIS];
    this.totalSteps = this.steps.length;
    this.currentStep = 0;
    this.progress = 0;
    this.cancelCallback = config.onCancel;
    this.startTime = Date.now();
    this.estimatedDuration = config.estimatedTime ? config.estimatedTime * 1000 : null;

    // Create modal if not exists
    if (!this.overlay) {
      console.log('[TickerModal] Creating modal (overlay not exists)');
      this.createModal();
    } else {
      console.log('[TickerModal] Reusing existing modal overlay');
    }

    // Update content
    this.titleElement.textContent = config.title;
    this.cancelButton.textContent = config.cancelText;
    this.cancelButton.style.display = config.showCancel ? 'inline-flex' : 'none';

    // Initialize step indicator
    this.renderStepIndicator();

    // Set initial operation
    this.updateMessage(this.steps[0]);

    // Initialize quote rotation
    this.startQuoteRotation();

    // Update time estimate
    this.updateTimeEstimate();

    // Add to DOM
    console.log('[TickerModal] Appending overlay to body...');
    document.body.appendChild(this.overlay);
    console.log('[TickerModal] Overlay appended, setting body overflow');
    document.body.style.overflow = 'hidden'; // Prevent body scroll

    // Add keyboard listener
    document.addEventListener('keydown', this.handleKeydown);

    // Animate in
    this.isOpen = true;
    console.log('[TickerModal] isOpen set to true, starting animation');

    if (!prefersReducedMotion()) {
      console.log('[TickerModal] Animating with reduced motion = false');
      // Animate overlay
      const overlayAnim = animate(this.overlay, [{ opacity: 0 }, { opacity: 1 }], {
        duration: DURATION_BASE,
        easing: EASING_SMOOTH
      });
      console.log('[TickerModal] Overlay animation started:', overlayAnim);

      // Animate modal
      const modalAnim = animate(this.modal, [
        { opacity: 0, transform: 'scale(0.9)' },
        { opacity: 1, transform: 'scale(1)' }
      ], {
        duration: DURATION_DRAMATIC,
        easing: EASING_DRAMATIC
      });
      console.log('[TickerModal] Modal animation started:', modalAnim);

      // Animate panda bounce
      this.startPandaAnimation();

      // Safety fallback: ensure visibility even if animation fails
      setTimeout(() => {
        if (this.overlay && this.isOpen) {
          const currentOpacity = parseFloat(this.overlay.style.opacity || window.getComputedStyle(this.overlay).opacity);
          if (currentOpacity < 0.5) {
            console.warn('[TickerModal] Animation may have failed, forcing visibility');
            this.overlay.style.opacity = '1';
            if (this.modal) {
              this.modal.style.opacity = '1';
              this.modal.style.transform = 'scale(1)';
            }
          }
        }
      }, 100);
    } else {
      console.log('[TickerModal] Reduced motion enabled, setting opacity directly');
      this.overlay.style.opacity = '1';
      this.modal.style.opacity = '1';
      this.modal.style.transform = 'scale(1)';
    }

    // Start time update interval
    this.timeInterval = setInterval(() => this.updateTimeEstimate(), 1000);
    console.log('[TickerModal] Time interval started');

    // Focus management
    this.cancelButton.focus();
    console.log('[TickerModal] Focus set to cancel button');

    console.log('[TickerModal] showTicker complete, modal should be visible');
    return this;
  }

  /**
   * Updates the progress ring and step indicator
   * @param {number} percent - Progress percentage (0-100)
   * @param {number} step - Current step index (optional, auto-calculated from percent if not provided)
   * @returns {TickerModal} this instance for chaining
   * 
   * @example
   * tickerModal.updateProgress(50, 3); // 50% complete, on step 3
   * tickerModal.updateProgress(75);    // 75% complete, step auto-calculated
   */
  updateProgress(percent, step = null) {
    if (!this.isOpen) {
      console.warn('TickerModal is not open');
      return this;
    }

    // Clamp percentage
    this.progress = Math.max(0, Math.min(100, percent));

    // Calculate step if not provided
    if (step === null) {
      this.currentStep = Math.floor((this.progress / 100) * this.totalSteps);
    } else {
      this.currentStep = Math.max(0, Math.min(step, this.totalSteps - 1));
    }

    // Update progress ring
    const circumference = 2 * Math.PI * 54; // r = 54
    const offset = circumference - (this.progress / 100) * circumference;
    this.progressCircle.style.strokeDashoffset = offset;

    // Update step indicator
    this.updateStepIndicator();

    // Update operation text based on step
    if (this.steps[this.currentStep]) {
      this.updateMessage(this.steps[this.currentStep]);
    }

    // Update panda expression based on progress
    this.updatePandaExpression();

    return this;
  }

  /**
   * Updates the current operation message with typewriter effect
   * @param {string} message - The message to display
   * @returns {TickerModal} this instance for chaining
   * 
   * @example
   * tickerModal.updateMessage('Processing image...');
   */
  updateMessage(message) {
    if (!this.isOpen || !message) return this;

    // Clear existing typewriter
    if (this.typewriterInterval) {
      clearInterval(this.typewriterInterval);
    }

    // Typewriter effect
    let charIndex = 0;
    this.operationElement.textContent = '';

    if (prefersReducedMotion()) {
      this.operationElement.textContent = message;
    } else {
      this.typewriterInterval = setInterval(() => {
        if (charIndex < message.length) {
          this.operationElement.textContent += message.charAt(charIndex);
          charIndex++;
        } else {
          clearInterval(this.typewriterInterval);
        }
      }, 30);
    }

    return this;
  }

  /**
   * Closes the ticker modal
   * @param {object} options - Close options
   * @param {boolean} options.animate - Whether to animate close (default: true)
   * @returns {Promise<void>} Resolves when modal is closed
   * 
   * @example
   * await tickerModal.closeTicker();
   * tickerModal.closeTicker({ animate: false });
   */
  async closeTicker(options = {}) {
    const { animate: shouldAnimate = true } = options;

    if (!this.isOpen) {
      return Promise.resolve();
    }

    // Clear intervals
    this.clearIntervals();

    // Remove keyboard listener
    document.removeEventListener('keydown', this.handleKeydown);

    if (shouldAnimate && !prefersReducedMotion()) {
      // Animate out
      const modalAnim = animate(this.modal, [
        { opacity: 1, transform: 'scale(1)' },
        { opacity: 0, transform: 'scale(0.95)' }
      ], {
        duration: DURATION_BASE,
        easing: EASING_SMOOTH
      });

      const overlayAnim = animate(this.overlay, [{ opacity: 1 }, { opacity: 0 }], {
        duration: DURATION_FAST,
        easing: EASING_SMOOTH
      });

      // Wait for animations
      if (modalAnim) await modalAnim.finished.catch(() => {});
      if (overlayAnim) await overlayAnim.finished.catch(() => {});
    }

    // Remove from DOM
    if (this.overlay && this.overlay.parentNode) {
      this.overlay.parentNode.removeChild(this.overlay);
    }

    // Restore body scroll
    document.body.style.overflow = '';

    this.isOpen = false;
    this.currentStep = 0;
    this.progress = 0;

    return Promise.resolve();
  }

  /**
   * Sets or updates the cancel callback
   * @param {function} callback - Function to call when user cancels
   * @returns {TickerModal} this instance for chaining
   * 
   * @example
   * tickerModal.onCancel(() => {
   *   console.log('User cancelled processing');
   *   abortProcessing();
   * });
   */
  onCancel(callback) {
    if (typeof callback === 'function') {
      this.cancelCallback = callback;
    }
    return this;
  }

  /**
   * Changes the modal type dynamically
   * @param {string} type - 'analysis' or 'reel'
   * @returns {TickerModal} this instance for chaining
   * 
   * @example
   * tickerModal.setType('reel');
   */
  setType(type) {
    if (!Object.values(MODAL_TYPES).includes(type)) {
      console.warn(`Invalid type: ${type}. Using 'analysis'`);
      type = MODAL_TYPES.ANALYSIS;
    }

    this.currentType = type;
    this.steps = DEFAULT_STEPS[type];
    this.totalSteps = this.steps.length;
    this.currentStep = 0;

    // Reset quote rotation with new type
    this.startQuoteRotation();

    // Re-render step indicator
    this.renderStepIndicator();

    return this;
  }

  /**
   * Gets the current progress percentage
   * @returns {number} Current progress (0-100)
   */
  getProgress() {
    return this.progress;
  }

  /**
   * Gets the current step index
   * @returns {number} Current step index
   */
  getCurrentStep() {
    return this.currentStep;
  }

  /**
   * Checks if the modal is currently open
   * @returns {boolean} True if open
   */
  isVisible() {
    return this.isOpen;
  }

  // ========================================
  // Private Methods
  // ========================================

  /**
   * Handles cancel button click
   * @private
   */
  handleCancel() {
    if (typeof this.cancelCallback === 'function') {
      this.cancelCallback();
    }
    this.closeTicker();
  }

  /**
   * Handles keyboard events
   * @private
   */
  handleKeydown(e) {
    if (e.key === 'Escape') {
      // Allow escape to cancel, but show confirmation if processing
      if (this.progress < 100 && this.progress > 0) {
        this.handleCancel();
      } else {
        this.closeTicker();
      }
    }
  }

  /**
   * Renders the step indicator dots
   * @private
   */
  renderStepIndicator() {
    this.stepIndicator.innerHTML = '';

    for (let i = 0; i < this.totalSteps; i++) {
      const dot = document.createElement('div');
      dot.className = 'ticker-step-dot';
      dot.style.cssText = STYLES.stepDot;
      dot.setAttribute('aria-hidden', 'true');
      this.stepIndicator.appendChild(dot);
    }

    this.updateStepIndicator();
  }

  /**
   * Updates step indicator visual state
   * @private
   */
  updateStepIndicator() {
    const dots = this.stepIndicator.querySelectorAll('.ticker-step-dot');

    dots.forEach((dot, index) => {
      dot.style.cssText = STYLES.stepDot;

      if (index < this.currentStep) {
        dot.style.cssText += STYLES.stepDotCompleted;
      } else if (index === this.currentStep) {
        dot.style.cssText += STYLES.stepDotActive;
      }
    });
  }

  /**
   * Starts the quote rotation
   * @private
   */
  startQuoteRotation() {
    // Clear existing interval
    if (this.quoteInterval) {
      clearInterval(this.quoteInterval);
    }

    // Set initial quote
    this.updateQuote();

    // Rotate every 3 seconds
    this.quoteInterval = setInterval(this.updateQuote, 3000);
  }

  /**
   * Updates the displayed quote
   * @private
   */
  updateQuote() {
    let quote;

    if (this.currentType === MODAL_TYPES.ANALYSIS) {
      quote = getAnalysisStep(Math.floor(Math.random() * 10));
    } else if (this.currentType === MODAL_TYPES.REEL) {
      quote = getReelStep(Math.floor(Math.random() * 10));
    } else {
      quote = getRandomQuote(QUOTE_CATEGORIES.GENERAL);
    }

    this.currentQuote = quote;

    // Fade out, change text, fade in
    if (!prefersReducedMotion() && this.quoteElement) {
      animate(this.quoteElement, [{ opacity: 1 }, { opacity: 0 }], {
        duration: DURATION_FAST,
        easing: EASING_SMOOTH,
        onComplete: () => {
          this.quoteElement.textContent = quote;
          animate(this.quoteElement, [{ opacity: 0 }, { opacity: 1 }], {
            duration: DURATION_FAST,
            easing: EASING_SMOOTH
          });
        }
      });
    } else if (this.quoteElement) {
      this.quoteElement.textContent = quote;
    }
  }

  /**
   * Updates the time estimate display
   * @private
   */
  updateTimeEstimate() {
    if (!this.estimatedDuration) {
      this.timeElement.textContent = '';
      return;
    }

    const elapsed = Date.now() - this.startTime;
    const remaining = Math.max(0, this.estimatedDuration - elapsed);
    const remainingSeconds = Math.ceil(remaining / 1000);

    if (remainingSeconds <= 0) {
      this.timeElement.textContent = 'Almost done...';
    } else {
      const seconds = remainingSeconds % 60;
      const minutes = Math.floor(remainingSeconds / 60);

      if (minutes > 0) {
        this.timeElement.textContent = `About ${minutes}m ${seconds}s remaining`;
      } else {
        this.timeElement.textContent = `About ${seconds}s remaining`;
      }
    }
  }

  /**
   * Starts the panda bounce animation
   * @private
   */
  startPandaAnimation() {
    if (!this.pandaEmoji || prefersReducedMotion()) return;

    // Gentle bounce animation
    this.pandaAnimation = animate(this.pandaEmoji, [
      { transform: 'translate(-50%, -50%) scale(1)' },
      { transform: 'translate(-50%, -55%) scale(1.05)' },
      { transform: 'translate(-50%, -50%) scale(1)' }
    ], {
      duration: 2000,
      easing: EASING_SPRING,
      iterations: Infinity
    });
  }

  /**
   * Updates panda expression based on progress
   * @private
   */
  updatePandaExpression() {
    const pandaStates = ['🐼', '😋', '🤔', '🧐', '🎉'];
    const stateIndex = Math.floor((this.progress / 100) * (pandaStates.length - 1));

    if (this.pandaEmoji) {
      this.pandaEmoji.textContent = pandaStates[stateIndex];
    }
  }

  /**
   * Shakes the modal to indicate it cannot be dismissed
   * @private
   */
  shakeModal() {
    if (!this.modal || prefersReducedMotion()) return;

    animate(this.modal, [
      { transform: 'translateX(0)' },
      { transform: 'translateX(-10px)' },
      { transform: 'translateX(10px)' },
      { transform: 'translateX(-10px)' },
      { transform: 'translateX(10px)' },
      { transform: 'translateX(0)' }
    ], {
      duration: DURATION_BASE,
      easing: EASING_SMOOTH
    });
  }

  /**
   * Clears all intervals
   * @private
   */
  clearIntervals() {
    if (this.quoteInterval) {
      clearInterval(this.quoteInterval);
      this.quoteInterval = null;
    }
    if (this.typewriterInterval) {
      clearInterval(this.typewriterInterval);
      this.typewriterInterval = null;
    }
    if (this.timeInterval) {
      clearInterval(this.timeInterval);
      this.timeInterval = null;
    }
    if (this.pandaAnimation) {
      this.pandaAnimation.cancel();
      this.pandaAnimation = null;
    }
  }
}

// ========================================
// Singleton Instance
// ========================================

const tickerModal = new TickerModal();

// ========================================
// Named Exports
// ========================================

export {
  TickerModal,
  MODAL_TYPES,
  showTicker,
  updateProgress,
  updateMessage,
  closeTicker,
  onCancel,
  setType,
  getProgress,
  getCurrentStep,
  isVisible
};

// ========================================
// Convenience Functions (using singleton)
// ========================================

function showTicker(options) {
  return tickerModal.showTicker(options);
}

function updateProgress(percent, step) {
  return tickerModal.updateProgress(percent, step);
}

function updateMessage(message) {
  return tickerModal.updateMessage(message);
}

function closeTicker(options) {
  return tickerModal.closeTicker(options);
}

function onCancel(callback) {
  return tickerModal.onCancel(callback);
}

function setType(type) {
  return tickerModal.setType(type);
}

function getProgress() {
  return tickerModal.getProgress();
}

function getCurrentStep() {
  return tickerModal.getCurrentStep();
}

function isVisible() {
  return tickerModal.isVisible();
}

// ========================================
// Exports
// ========================================

export default tickerModal;
