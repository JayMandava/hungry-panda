-- Phase 1: Foundation & Visual Direction Changes
INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(1, 'Visual Direction System', 'Foundation', 'completed', 'Define stronger art direction and brand system', 'New color palette: --brand-primary #ff6b6b, --bg-base #0a0a0f, layered surface system with --bg-elevated and --bg-card, border hierarchy with subtle transparency', 'frontend/dashboard.html, frontend/voice-styles.css', '89740c6');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(1, 'Typography Scale', 'Foundation', 'completed', 'Replace system-font with editorial type hierarchy', 'Defined --font-display and --font-mono, text scale from xs (11px) to 3xl (36px), font weights 400-700, letter-spacing for display', 'frontend/dashboard.html', '89740c6');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(1, 'Color System Rebalance', 'Foundation', 'completed', 'Reduce accent-color overuse', 'Restrained coral accent for primary actions only, semantic colors (--brand-success #66bb6a, --brand-info #42a5f5), subtle gradients, border hierarchy with rgba whites', 'frontend/dashboard.html, frontend/voice-styles.css', '89740c6');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(1, 'Page Hierarchy', 'Structure', 'completed', 'Create stronger hierarchy between major sections', 'Upload as hero (strongest presence), Queue as operational, Strategy as insight-led, Competitors/Hashtags as supporting panels', 'frontend/dashboard.html', '89740c6');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(1, 'Upload Hero Transformation', 'Components', 'completed', 'Turn upload card into signature action', 'Larger dropzone with --bg-hero gradient, 2px dashed border in accent color, ambient glow on hover, 80px animated icon, cleaner helper text', 'frontend/dashboard.html', '89740c6');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(1, 'Content Queue Redesign', 'Components', 'completed', 'Redesign queue rows for stronger scanning', 'Tab-based navigation (Pending/Scheduled/Posted), cleaner row design with subtle hover, status pills with semantic colors, slide-in animation', 'frontend/dashboard.html', '89740c6');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(1, 'Strategy Panel Premium Feel', 'Components', 'completed', 'Rework strategy card to feel insight-led', 'Editorial design with gradient background, badge system for theme, bullet list with check icons, better information hierarchy', 'frontend/dashboard.html', '89740c6');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(1, 'Header Redesign', 'Components', 'completed', 'Premium brand presence in header', '44px brand icon with gradient and glow, backdrop-filter blur, status badge with animated pulse dot, cleaner layout', 'frontend/dashboard.html', '89740c6');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(1, 'Metrics Cards Upgrade', 'Components', 'completed', 'Redesign metric cards to feel less generic', 'Mono numerals in --font-mono, top highlight line on hover, gradient text effect, 2px lift on hover, better label hierarchy', 'frontend/dashboard.html', '89740c6');

-- Phase 2: Mobile Optimizations & Polish
INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(2, 'M1: Mobile Header Presence', 'Mobile', 'completed', 'Give mobile header more presence and breathing room', 'Sticky position, larger brand icon (40px), hidden tagline on mobile, better top spacing with --space-5', 'frontend/dashboard.html', '8017be2');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(2, 'M2: Mobile Metrics Compactness', 'Mobile', 'completed', 'Make metrics more compact and less repetitive', '2x2 grid layout, smaller fonts (--text-xl for values), tighter spacing (--space-3 gap), reduced padding', 'frontend/dashboard.html', '8017be2');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(2, 'M3: Mobile Queue Action Density', 'Mobile', 'completed', 'Reduce action density in queue rows', 'Single primary action visible, progressive disclosure pattern, 32px action buttons, better tap targets', 'frontend/dashboard.html', '8017be2');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(2, 'M4: Mobile Pacing', 'Mobile', 'completed', 'Improve pacing between stacked cards', 'Reduced section margins (--space-5), better visual cadence, section entrance animations, spacing rhythm', 'frontend/dashboard.html', '8017be2');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(2, 'M5: Mobile Upload UX', 'Mobile', 'completed', 'Make upload feel faster and more native', 'Compact hero sizing, native-feeling voice input, larger touch targets (44px), simplified helper text', 'frontend/dashboard.html', '8017be2');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(2, 'Safe Area Insets', 'Mobile', 'completed', 'Support for modern mobile devices', '@supports padding with env(safe-area-inset) for iPhone X+ notch and home indicator', 'frontend/dashboard.html', '8017be2');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(2, 'Touch Device Optimizations', 'Mobile', 'completed', 'Disable hover effects on touch devices', '@media (hover: none) to remove transforms, larger 44px touch targets on mobile', 'frontend/dashboard.html', '8017be2');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(2, 'Modal Design Upgrade', 'Components', 'completed', 'Upgrade AI recommendation modal presentation', 'Gradient header with sparkle icon, animated entry (scale+fade), variant cards with checkmarks, time badge with clock icon, improved hashtag display', 'frontend/dashboard.html', '324d00c');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(2, 'Thumbnail/Media Preview System', 'Components', 'completed', 'Replace repetitive placeholder icons', 'Smart preview loading actual images, content-type specific icons (🍳🥗🍽️🍰), video indicators, gradient overlays', 'frontend/dashboard.html', 'a13b19f');

-- Phase 3: Final Polish & Microcopy
INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(3, 'Microcopy Tone Refinement', 'Copy', 'completed', 'Polish interface language to product-grade', 'Updated 20+ toast messages, contextual empty states, clearer error messages, removed LLM-ish feel', 'frontend/dashboard.html', 'a2baf7e');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(3, 'Loading States - Skeletons', 'Animations', 'completed', 'Add skeleton loading animations', 'Shimmer effect with gradient animation, skeleton-text and skeleton-title classes, loading button states', 'frontend/dashboard.html', 'a2baf7e');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(3, 'Empty States Enhancement', 'Components', 'completed', 'Improve empty state presentations', 'Floating icon animation (3s ease-in-out), contextual messages per tab, fadeIn entrance', 'frontend/dashboard.html', 'a2baf7e');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(3, 'Button Micro-interactions', 'Animations', 'completed', 'Add button press and loading states', 'Active state scale(0.98), loading spinner overlay, gentle hover transitions', 'frontend/dashboard.html', 'a2baf7e');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(3, 'Section Entrance Animations', 'Animations', 'completed', 'Animate sections on page load', 'Staggered card entrance (0.05s delay each), section fadeIn with translateY, upload icon gentle pulse', 'frontend/dashboard.html', 'a2baf7e');

INSERT INTO changes (phase_id, item_name, category, status, description, implementation_details, files_modified, git_commit) VALUES
(3, 'iOS Font Size Fix', 'Mobile', 'completed', 'Prevent zoom on iOS inputs', '16px font-size on form inputs to prevent automatic zoom on focus', 'frontend/dashboard.html', 'a2baf7e');

-- Git Commits
INSERT INTO git_commits (hash, message, date, files_changed, insertions, deletions, phase_id) VALUES
('89740c6', 'Phase 1 UI Facelift: Premium design system with new color palette, typography, upload hero, redesigned queue, and strategy panel', '2026-04-20 14:00:00', 2, 1586, 1364, 1);

INSERT INTO git_commits (hash, message, date, files_changed, insertions, deletions, phase_id) VALUES
('8017be2', 'Phase 2 Mobile: Comprehensive mobile optimizations - header presence, compact metrics, reduced queue density, better pacing, native-feeling upload', '2026-04-20 15:30:00', 1, 367, 0, 2);

INSERT INTO git_commits (hash, message, date, files_changed, insertions, deletions, phase_id) VALUES
('324d00c', 'Phase 2 Modal: Premium modal design with gradient header, animated entry, variant cards with checkmarks, optimal time display', '2026-04-20 15:45:00', 1, 161, 23, 2);

INSERT INTO git_commits (hash, message, date, files_changed, insertions, deletions, phase_id) VALUES
('a13b19f', 'Phase 2 Thumbnails: Smart preview system with content-type icons, image loading support, video indicators, and contextual icons', '2026-04-20 16:00:00', 1, 86, 3, 2);

INSERT INTO git_commits (hash, message, date, files_changed, insertions, deletions, phase_id) VALUES
('a2baf7e', 'Phase 3 Polish: Refined microcopy, improved loading states with skeletons, added floating empty states, button micro-interactions, section entrance animations', '2026-04-20 16:30:00', 1, 145, 20, 3);

-- Metrics
INSERT INTO metrics (metric_name, metric_value, metric_type) VALUES
('Total Phases', '3', 'count');

INSERT INTO metrics (metric_name, metric_value, metric_type) VALUES
('Total Changes', '23', 'count');

INSERT INTO metrics (metric_name, metric_value, metric_type) VALUES
('Files Modified', '2', 'count');

INSERT INTO metrics (metric_name, metric_value, metric_type) VALUES
('Total Lines Added', '2345', 'count');

INSERT INTO metrics (metric_name, metric_value, metric_type) VALUES
('Total Lines Removed', '1410', 'count');

INSERT INTO metrics (metric_name, metric_value, metric_type) VALUES
('Net Lines Changed', '935', 'count');

INSERT INTO metrics (metric_name, metric_value, metric_type) VALUES
('Completion Percentage', '100', 'percentage');

INSERT INTO metrics (metric_name, metric_value, metric_type) VALUES
('Mobile Issues Fixed', '5', 'count');

INSERT INTO metrics (metric_name, metric_value, metric_type) VALUES
('Design Uplift Items', '17', 'count');

INSERT INTO metrics (metric_name, metric_value, metric_type) VALUES
('Toast Messages Updated', '20', 'count');

INSERT INTO metrics (metric_name, metric_value, metric_type) VALUES
('New CSS Variables', '50+', 'count');

INSERT INTO metrics (metric_name, metric_value, metric_type) VALUES
('Animations Added', '12', 'count');

-- Summary
INSERT INTO summary (total_phases, total_changes, total_files_modified, total_lines_added, total_lines_removed, completion_percentage) VALUES
(3, 23, 2, 2345, 1410, 100);
