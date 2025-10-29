# Debt Profile - Design System Documentation

## Overview
This document outlines the complete design system used in the Debt Profile application, based on the Personal Dashboard design inspiration. This design system can be reused for future projects requiring a modern, financial-focused interface.

## 🎨 Color Palette

### Primary Colors
- **Primary**: `#4F46E5` (Violet/Indigo)
- **Accent Gradient**: `from-[#4F46E5] to-[#60A5FA]` (Violet to Blue)
- **Secondary**: `#3B82F6` (Blue)
- **Accent**: `#EC4899` (Pink)

### Neutral Colors
- **Background**: `#F8FAFC` (Light Gray)
- **Surface/Card**: `#FFFFFF` (White)
- **Text Primary**: `#111827` (Dark Gray)
- **Text Secondary**: `#6B7280` (Medium Gray)
- **Border**: `#E5E7EB` (Light Border)

### Semantic Colors
- **Success**: `#10B981` (Emerald)
- **Warning**: `#F59E0B` (Amber)
- **Error**: `#EF4444` (Red)
- **Info**: `#3B82F6` (Blue)

### Chart Colors
- **Shopping/Credit Cards**: `#6366F1` (Violet)
- **Travel/Student Loans**: `#3B82F6` (Blue)
- **Food/Personal Loans**: `#EC4899` (Pink)

## 📐 Layout & Spacing

### Grid System
- **Container Max Width**: 1440px
- **Columns**: 12-column responsive grid
- **Gutter**: 32px between main sections
- **Breakpoints**:
  - Mobile: < 768px (stack columns)
  - Tablet: 768px - 1024px
  - Desktop: > 1024px

### Spacing Scale
- **4px**: xs (small elements)
- **8px**: sm (component padding)
- **12px**: md (card padding)
- **16px**: lg (section spacing)
- **24px**: xl (major sections)
- **32px**: 2xl (gutters)

### Component Spacing
- **Card Padding**: 24-32px
- **Element Spacing**: 16px between elements
- **List Items**: 12px between items

## 🧱 Typography

### Font Family
- **Primary**: "Inter", sans-serif (Google Fonts)
- **Fallback**: system-ui, -apple-system, sans-serif

### Font Weights
- **Regular**: 400
- **Medium**: 500
- **Bold**: 700

### Font Sizes
- **Heading 1**: 32px (2xl)
- **Heading 2**: 24px (xl)
- **Heading 3**: 18px (lg)
- **Body Large**: 16px (base)
- **Body**: 14px (sm)
- **Small**: 12px (xs)

### Line Heights
- **Headings**: 1.2 (tight)
- **Body**: 1.5 (comfortable)
- **Small Text**: 1.4

## 🎯 Components

### Cards
```css
/* Base Card Styles */
.card {
  background: #FFFFFF;
  border-radius: 12px;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  padding: 24px;
}

/* Elevated Card */
.card-elevated {
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
```

### Buttons
```css
/* Primary Button */
.btn-primary {
  background: linear-gradient(135deg, #4F46E5 0%, #60A5FA 100%);
  color: white;
  border-radius: 12px;
  padding: 12px 24px;
  font-weight: 500;
  transition: all 0.2s ease;
}

/* Secondary Button */
.btn-secondary {
  background: #F3F4F6;
  color: #374151;
  border-radius: 12px;
  padding: 12px 24px;
  font-weight: 500;
}
```

### Wallet Card
```css
.wallet-card {
  background: linear-gradient(135deg, #4F46E5 0%, #60A5FA 100%);
  border-radius: 16px;
  padding: 24px;
  color: white;
  position: relative;
  overflow: hidden;
}

/* Decorative elements */
.wallet-card::before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  width: 128px;
  height: 128px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  transform: translate(32px, -32px);
}
```

### Navigation
```css
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  transition: background-color 0.2s ease;
}

.nav-item:hover {
  background: #F3F4F6;
}

.nav-item.active {
  background: rgba(79, 70, 229, 0.1);
  color: #4F46E5;
  font-weight: 500;
}
```

## 📊 Charts

### Donut Chart Configuration
```javascript
{
  type: 'doughnut',
  data: {
    datasets: [{
      data: [1200, 800, 400],
      backgroundColor: ['#6366F1', '#3B82F6', '#EC4899'],
      borderWidth: 0,
      cutout: '70%'
    }]
  },
  options: {
    responsive: true,
    plugins: {
      legend: {
        position: 'bottom',
        labels: { padding: 20 }
      }
    }
  }
}
```

### Line Chart Configuration
```javascript
{
  type: 'line',
  data: {
    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    datasets: [{
      data: [85.50, 92.30, 78.90, 122.50, 95.20, 110.80, 88.40],
      borderColor: '#8B5CF6',
      backgroundColor: 'rgba(139, 92, 246, 0.1)',
      borderWidth: 3,
      tension: 0.4,
      fill: true,
      pointRadius: 6,
      pointHoverRadius: 8
    }]
  },
  options: {
    responsive: true,
    scales: {
      y: {
        ticks: {
          callback: function(value) {
            return '$' + value.toFixed(2);
          }
        }
      }
    }
  }
}
```

## 📱 Responsive Design

### Breakpoint Strategy
- **Mobile First**: Design for mobile, enhance for larger screens
- **Flexible Grid**: Use CSS Grid and Flexbox for layouts
- **Responsive Images**: Charts and components scale appropriately
- **Touch Friendly**: Minimum 44px touch targets

### Mobile Optimizations
```css
@media (max-width: 768px) {
  .container {
    padding-left: 16px;
    padding-right: 16px;
  }

  .grid-cols-3 {
    grid-template-columns: 1fr;
  }

  .card {
    padding: 16px;
  }
}
```

## 🎭 Animations & Interactions

### Transitions
```css
/* Smooth transitions for interactive elements */
.btn, .nav-item, .card:hover {
  transition: all 0.2s ease-in-out;
}

/* Hover effects */
.btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
}
```

### Loading States
```css
.loading {
  opacity: 0.7;
  pointer-events: none;
}

.spinner {
  border: 2px solid #F3F4F6;
  border-top: 2px solid #4F46E5;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
```

## ♿ Accessibility

### Color Contrast
- Text on background: Minimum 4.5:1 ratio
- Large text: Minimum 3:1 ratio
- Interactive elements: Clear focus indicators

### Semantic HTML
- Proper heading hierarchy (h1 → h6)
- Semantic landmarks (header, nav, main, aside)
- ARIA labels where needed

### Keyboard Navigation
- Tab order follows logical flow
- Focus indicators visible
- Keyboard shortcuts for common actions

## 🛠 Implementation Guidelines

### CSS Architecture
- Use Tailwind CSS for utility classes
- Custom CSS for complex components
- CSS custom properties for theme colors
- Mobile-first responsive design

### JavaScript
- Vanilla JavaScript with modern ES6+ features
- Chart.js for data visualization
- HTMX for dynamic interactions
- Alpine.js for reactive components

### File Structure
```
templates/
├── base/
│   └── base.html
├── auth/
│   ├── login.html
│   └── signup.html
├── loans/
│   ├── dashboard.html
│   └── loan_form.html
└── ...

static/
├── css/
│   └── main.css
└── js/
    └── main.js
```

## 📋 Usage Checklist

### For New Components
- [ ] Follow color palette
- [ ] Use consistent spacing scale
- [ ] Implement responsive design
- [ ] Add hover/focus states
- [ ] Test accessibility
- [ ] Document in this guide

### For New Pages
- [ ] Use base template
- [ ] Follow 3-column layout when applicable
- [ ] Implement mobile responsiveness
- [ ] Add proper semantic HTML
- [ ] Test across devices

## 🔄 Maintenance

### Updating the Design System
1. Document changes in this file
2. Update CSS custom properties
3. Test across all components
4. Update component documentation
5. Communicate changes to team

### Version History
- **v1.0**: Initial design system based on Personal Dashboard inspiration
- **Components**: Cards, buttons, navigation, charts, wallet card
- **Colors**: Violet-blue primary palette
- **Typography**: Inter font family
- **Layout**: 3-column responsive grid
- **v1.1 (2025-10-29)**: Enhanced UX with dynamic data display and improved legal disclaimer placement
- **New Features**: Dynamic expense breakdown, clickable navigation elements, bottom-positioned legal notices
- **UX Improvements**: Better information hierarchy, improved accessibility, enhanced mobile experience

---

This design system provides a solid foundation for building modern, financial-focused web applications. It emphasizes usability, accessibility, and visual consistency while remaining flexible for future enhancements.