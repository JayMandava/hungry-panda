/**
 * Hungry Panda - Animation Utilities Library
 * Production-ready animation utilities using Web Animations API
 * 
 * @module animations
 * @version 1.0.0
 * @author Hungry Panda UX Team
 */

// ========================================
// EASING FUNCTIONS
// ========================================

/**
 * Spring easing - Bouncy, natural motion
 * Perfect for interactive elements and notifications
 */
export const EASING_SPRING = 'cubic-bezier(0.34, 1.56, 0.64, 1)';

/**
 * Smooth easing - Elegant, refined transitions
 * Default for most UI transitions
 */
export const EASING_SMOOTH = 'cubic-bezier(0.4, 0, 0.2, 1)';

/**
 * Dramatic easing - Bold, cinematic entrances
 * For hero elements and modals
 */
export const EASING_DRAMATIC = 'cubic-bezier(0.16, 1, 0.3, 1)';

/**
 * Bounce easing - Playful, energetic
 * For success states and celebrations
 */
export const EASING_BOUNCE = 'cubic-bezier(0.68, -0.55, 0.265, 1.55)';

/**
 * Linear easing - For continuous animations
 */
export const EASING_LINEAR = 'linear';

/**
 * Decelerate easing - Natural slow-down
 * For exits and dismissals
 */
export const EASING_DECELERATE = 'cubic-bezier(0, 0, 0.2, 1)';

// ========================================
// DURATION CONSTANTS (in milliseconds)
// ========================================

/** Instant - For immediate feedback */
export const DURATION_INSTANT = 100;

/** Fast - Hover states, micro-interactions */
export const DURATION_FAST = 150;

/** Base - Standard transitions */
export const DURATION_BASE = 250;

/** Slow - Page transitions, reveals */
export const DURATION_SLOW = 400;

/** Dramatic - Hero entrances, modals */
export const DURATION_DRAMATIC = 600;

// ========================================
// CORE ANIMATION FUNCTION
// ========================================

/**
 * Animates an element using Web Animations API with fallback support
 * 
 * @param {HTMLElement} element - Element to animate
 * @param {Keyframe[]|PropertyIndexedKeyframes} keyframes - Animation keyframes
 * @param {KeyframeAnimationOptions} options - Animation options
 * @returns {Animation|null} The Animation object or null if reduced motion is preferred
 * 
 * @example
 * animate(card, 
 *   [{ opacity: 0, transform: 'translateY(20px)' }, 
 *    { opacity: 1, transform: 'translateY(0)' }],
 *   { duration: 300, easing: EASING_SMOOTH }
 * )
 */
export function animate(element, keyframes, options = {}) {
  // Respect user's motion preferences
  if (prefersReducedMotion()) {
    // Apply final state immediately without animation
    if (keyframes && keyframes.length > 0) {
      const finalKeyframe = keyframes[keyframes.length - 1];
      Object.assign(element.style, finalKeyframe);
    }
    return null;
  }

  // Default options
  const defaultOptions = {
    duration: DURATION_BASE,
    easing: EASING_SMOOTH,
    fill: 'forwards',
    ...options
  };

  try {
    const animation = element.animate(keyframes, defaultOptions);
    
    // Handle promise for completion callbacks
    if (options.onComplete || options.onFinish) {
      animation.finished
        .then(() => {
          options.onComplete?.(animation);
          options.onFinish?.(animation);
        })
        .catch(() => {
          // Animation was cancelled, ignore
        });
    }

    return animation;
  } catch (error) {
    console.warn('Web Animations API not supported, using fallback', error);
    
    // CSS transition fallback
    applyCSSFallback(element, keyframes, defaultOptions);
    return null;
  }
}

/**
 * CSS transition fallback for browsers without WAAPI
 * @private
 */
function applyCSSFallback(element, keyframes, options) {
  const finalKeyframe = keyframes[keyframes.length - 1];
  const initialKeyframe = keyframes[0];
  
  // Apply initial state
  Object.assign(element.style, {
    transition: `all ${options.duration}ms ${options.easing}`,
    ...initialKeyframe
  });
  
  // Force reflow
  element.offsetHeight;
  
  // Apply final state
  Object.assign(element.style, finalKeyframe);
  
  // Cleanup after animation
  setTimeout(() => {
    element.style.transition = '';
    options.onComplete?.();
  }, options.duration);
}

// ========================================
// PAGE TRANSITIONS
// ========================================

/**
 * Animates page enter/exit transitions
 * 
 * @param {string} direction - 'enter' or 'exit'
 * @param {HTMLElement} [element=document.body] - Element to animate
 * @param {object} options - Animation options
 * @returns {Animation|null}
 * 
 * @example
 * // On page load
 * pageTransition('enter');
 * 
 * // Before navigation
 * await pageTransition('exit').finished;
 * router.navigate('/new-page');
 */
export function pageTransition(direction, element = document.body, options = {}) {
  const isEnter = direction === 'enter';
  
  const keyframes = isEnter ? [
    { opacity: 0, transform: 'translateY(20px) scale(0.98)' },
    { opacity: 1, transform: 'translateY(0) scale(1)' }
  ] : [
    { opacity: 1, transform: 'translateY(0) scale(1)' },
    { opacity: 0, transform: 'translateY(-20px) scale(0.98)' }
  ];

  const defaultOptions = {
    duration: isEnter ? DURATION_DRAMATIC : DURATION_SLOW,
    easing: EASING_DRAMATIC,
    fill: 'forwards',
    ...options
  };

  return animate(element, keyframes, defaultOptions);
}

// ========================================
// MODAL ANIMATIONS
// ========================================

/**
 * Animates modal backdrop entrance
 * 
 * @param {HTMLElement} backdrop - Backdrop element
 * @param {object} options - Animation options
 * @returns {Animation|null}
 */
export function modalBackdropEnter(backdrop, options = {}) {
  const keyframes = [
    { opacity: 0 },
    { opacity: 1 }
  ];

  return animate(backdrop, keyframes, {
    duration: DURATION_BASE,
    easing: EASING_SMOOTH,
    ...options
  });
}

/**
 * Animates modal backdrop exit
 * 
 * @param {HTMLElement} backdrop - Backdrop element
 * @param {object} options - Animation options
 * @returns {Animation|null}
 */
export function modalBackdropExit(backdrop, options = {}) {
  const keyframes = [
    { opacity: 1 },
    { opacity: 0 }
  ];

  return animate(backdrop, keyframes, {
    duration: DURATION_FAST,
    easing: EASING_SMOOTH,
    ...options
  });
}

/**
 * Animates modal content entrance
 * 
 * @param {HTMLElement} modal - Modal element
 * @param {object} options - Animation options
 * @returns {Animation|null}
 */
export function modalEnter(modal, options = {}) {
  const keyframes = [
    { 
      opacity: 0, 
      transform: 'translateY(40px) scale(0.95)',
      filter: 'blur(10px)'
    },
    { 
      opacity: 1, 
      transform: 'translateY(0) scale(1)',
      filter: 'blur(0px)'
    }
  ];

  return animate(modal, keyframes, {
    duration: DURATION_DRAMATIC,
    easing: EASING_DRAMATIC,
    ...options
  });
}

/**
 * Animates modal content exit
 * 
 * @param {HTMLElement} modal - Modal element
 * @param {object} options - Animation options
 * @returns {Animation|null}
 */
export function modalExit(modal, options = {}) {
  const keyframes = [
    { 
      opacity: 1, 
      transform: 'translateY(0) scale(1)',
      filter: 'blur(0px)'
    },
    { 
      opacity: 0, 
      transform: 'translateY(20px) scale(0.95)',
      filter: 'blur(10px)'
    }
  ];

  return animate(modal, keyframes, {
    duration: DURATION_BASE,
    easing: EASING_SMOOTH,
    ...options
  });
}

// ========================================
// STAGGER ANIMATIONS
// ========================================

/**
 * Animates children elements with staggered delays
 * 
 * @param {HTMLElement} container - Parent container
 * @param {string} childSelector - CSS selector for children
 * @param {number} delay - Delay between each child (in ms)
 * @param {object} options - Animation options
 * @returns {Animation[]} Array of Animation objects
 * 
 * @example
 * staggerChildren(queueList, '.queue-item', 60, {
 *   keyframes: [
 *     { opacity: 0, transform: 'translateY(20px)' },
 *     { opacity: 1, transform: 'translateY(0)' }
 *   ],
 *   duration: 400
 * });
 */
export function staggerChildren(container, childSelector, delay = 60, options = {}) {
  const children = container.querySelectorAll(childSelector);
  const animations = [];
  
  const defaultKeyframes = [
    { opacity: 0, transform: 'translateY(20px) scale(0.98)' },
    { opacity: 1, transform: 'translateY(0) scale(1)' }
  ];

  children.forEach((child, index) => {
    const animation = animate(child, options.keyframes || defaultKeyframes, {
      duration: DURATION_BASE,
      easing: EASING_DRAMATIC,
      delay: index * delay,
      fill: 'forwards',
      ...options
    });
    
    if (animation) {
      animations.push(animation);
    }
  });

  return animations;
}

// ========================================
// ACCESSIBILITY
// ========================================

/**
 * Checks if user prefers reduced motion
 * Respects system accessibility settings
 * 
 * @returns {boolean} True if reduced motion is preferred
 */
export function prefersReducedMotion() {
  if (typeof window === 'undefined') return false;
  
  const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  return mediaQuery.matches;
}

/**
 * Watches for changes in motion preference
 * 
 * @param {function} callback - Function to call when preference changes
 * @returns {function} Unsubscribe function
 */
export function watchReducedMotion(callback) {
  if (typeof window === 'undefined') return () => {};
  
  const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  
  const handler = (event) => callback(event.matches);
  
  // Modern API
  if (mediaQuery.addEventListener) {
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }
  
  // Legacy API
  mediaQuery.addListener(handler);
  return () => mediaQuery.removeListener(handler);
}

// ========================================
// UTILITY ANIMATIONS
// ========================================

/**
 * Pulse animation for attention/notification
 * 
 * @param {HTMLElement} element - Element to pulse
 * @param {object} options - Animation options
 * @returns {Animation|null}
 */
export function pulse(element, options = {}) {
  const keyframes = [
    { transform: 'scale(1)' },
    { transform: 'scale(1.05)' },
    { transform: 'scale(1)' }
  ];

  return animate(element, keyframes, {
    duration: DURATION_SLOW,
    easing: EASING_SPRING,
    iterations: options.iterations || 2,
    ...options
  });
}

/**
 * Shake animation for error/invalid states
 * 
 * @param {HTMLElement} element - Element to shake
 * @param {object} options - Animation options
 * @returns {Animation|null}
 */
export function shake(element, options = {}) {
  const keyframes = [
    { transform: 'translateX(0)' },
    { transform: 'translateX(-10px)' },
    { transform: 'translateX(10px)' },
    { transform: 'translateX(-10px)' },
    { transform: 'translateX(10px)' },
    { transform: 'translateX(0)' }
  ];

  return animate(element, keyframes, {
    duration: DURATION_BASE,
    easing: EASING_LINEAR,
    ...options
  });
}

/**
 * Success checkmark animation
 * 
 * @param {HTMLElement} element - Element to animate
 * @param {object} options - Animation options
 * @returns {Animation|null}
 */
export function successPop(element, options = {}) {
  const keyframes = [
    { transform: 'scale(0)', opacity: 0 },
    { transform: 'scale(1.2)', opacity: 1 },
    { transform: 'scale(1)', opacity: 1 }
  ];

  return animate(element, keyframes, {
    duration: DURATION_SLOW,
    easing: EASING_SPRING,
    ...options
  });
}

// ========================================
// SCROLL ANIMATIONS
// ========================================

/**
 * Reveal elements as they enter viewport
 * Uses IntersectionObserver for performance
 * 
 * @param {string} selector - CSS selector for elements to reveal
 * @param {object} options - Animation options
 * @returns {IntersectionObserver} Observer instance
 */
export function scrollReveal(selector, options = {}) {
  if (typeof window === 'undefined' || !('IntersectionObserver' in window)) {
    // Fallback: show all elements immediately
    document.querySelectorAll(selector).forEach(el => {
      el.style.opacity = '1';
      el.style.transform = 'none';
    });
    return null;
  }

  const defaultOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px',
    once: true,
    ...options
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        animate(entry.target, [
          { opacity: 0, transform: 'translateY(30px)' },
          { opacity: 1, transform: 'translateY(0)' }
        ], {
          duration: DURATION_SLOW,
          easing: EASING_DRAMATIC
        });

        if (defaultOptions.once) {
          observer.unobserve(entry.target);
        }
      }
    });
  }, defaultOptions);

  document.querySelectorAll(selector).forEach(el => observer.observe(el));
  return observer;
}

// ========================================
// BULK EXPORTS
// ========================================

/**
 * Animation presets for common use cases
 */
export const PRESETS = {
  /** Fade in from bottom */
  fadeInUp: {
    keyframes: [
      { opacity: 0, transform: 'translateY(20px)' },
      { opacity: 1, transform: 'translateY(0)' }
    ],
    options: { duration: DURATION_BASE, easing: EASING_SMOOTH }
  },
  
  /** Fade in from left */
  fadeInLeft: {
    keyframes: [
      { opacity: 0, transform: 'translateX(-20px)' },
      { opacity: 1, transform: 'translateX(0)' }
    ],
    options: { duration: DURATION_BASE, easing: EASING_SMOOTH }
  },
  
  /** Scale in with bounce */
  scaleIn: {
    keyframes: [
      { opacity: 0, transform: 'scale(0.9)' },
      { opacity: 1, transform: 'scale(1)' }
    ],
    options: { duration: DURATION_SLOW, easing: EASING_SPRING }
  },
  
  /** Subtle hover lift */
  hoverLift: {
    keyframes: [
      { transform: 'translateY(0)' },
      { transform: 'translateY(-4px)' }
    ],
    options: { duration: DURATION_FAST, easing: EASING_SMOOTH }
  }
};

/**
 * Apply a preset animation
 * 
 * @param {HTMLElement} element - Element to animate
 * @param {string} presetName - Name of preset from PRESETS
 * @param {object} overrideOptions - Options to override
 * @returns {Animation|null}
 */
export function applyPreset(element, presetName, overrideOptions = {}) {
  const preset = PRESETS[presetName];
  if (!preset) {
    console.warn(`Unknown preset: ${presetName}`);
    return null;
  }
  
  return animate(element, preset.keyframes, {
    ...preset.options,
    ...overrideOptions
  });
}

// Default export for convenience
export default {
  // Easings
  EASING_SPRING,
  EASING_SMOOTH,
  EASING_DRAMATIC,
  EASING_BOUNCE,
  EASING_LINEAR,
  EASING_DECELERATE,
  
  // Durations
  DURATION_INSTANT,
  DURATION_FAST,
  DURATION_BASE,
  DURATION_SLOW,
  DURATION_DRAMATIC,
  
  // Functions
  animate,
  pageTransition,
  modalBackdropEnter,
  modalBackdropExit,
  modalEnter,
  modalExit,
  staggerChildren,
  prefersReducedMotion,
  watchReducedMotion,
  pulse,
  shake,
  successPop,
  scrollReveal,
  
  // Presets
  PRESETS,
  applyPreset
};
