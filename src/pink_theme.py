"""Dark amethyst theme for AI VTuber System."""

THEME = {
    'bg_darkest': '#0b0b14',
    'bg_dark': '#13131f',
    'bg_medium': '#1c1c30',
    'bg_light': '#262640',
    'bg_lighter': '#323258',
    'primary': '#a78bfa',
    'primary_hover': '#c4b5fd',
    'primary_active': '#8b5cf6',
    'secondary': '#f472b6',
    'secondary_hover': '#f9a8d4',
    'secondary_active': '#ec4899',
    'accent': '#22d3ee',
    'accent_hover': '#67e8f9',
    'accent_active': '#06b6d4',
    'text_primary': '#f1f5f9',
    'text_secondary': '#a1a1aa',
    'text_tertiary': '#71717a',
    'text_disabled': '#52525b',
    'success': '#34d399',
    'warning': '#fbbf24',
    'error': '#fb7185',
    'info': '#60a5fa',
    'border': '#2e2e4a',
    'border_light': '#3e3e5e',
    'border_dark': '#1e1e32',
    'shadow': '#00000050',
    'overlay': '#0b0b1499',
    'button_primary': '#7c3aed',
    'button_secondary': '#262640',
    'button_success': '#059669',
    'button_danger': '#dc2626',
    'button_info': '#2563eb',
    'input_bg': '#1c1c30',
    'input_border': '#2e2e4a',
    'input_focus': '#a78bfa',
    'input_text': '#f1f5f9',
    'input_placeholder': '#71717a',
    'log_bg': '#0b0b14',
    'log_info': '#60a5fa',
    'log_warning': '#fbbf24',
    'log_error': '#fb7185',
    'log_success': '#34d399',
    'log_debug': '#71717a',
    'log_system': '#a78bfa',
    'tab_bg': '#1c1c30',
    'tab_selected': '#262640',
    'tab_hover': '#323258',
    'tab_text': '#a1a1aa',
    'tab_selected_text': '#f1f5f9',
    'progress_bg': '#1c1c30',
    'progress_fill': '#a78bfa',
    'progress_text': '#f1f5f9',
    'subtitle_bg': '#13131fcc',
    'subtitle_text': '#f1f5f9',
    'subtitle_border': '#a78bfa',
    'debugger_bg': '#0b0b14',
    'debugger_panel': '#13131f',
    'debugger_border': '#2e2e4a',
    'debugger_highlight': '#a78bfa',
    'annotation_target': '#34d399',
    'annotation_bbox': '#fbbf24',
    'annotation_drift': '#22d3ee',
    'annotation_text': '#f1f5f9',
}


def get_theme():
    return THEME.copy()


def apply_theme_to_widget(widget, widget_type='default'):
    t = get_theme()
    if widget_type == 'button':
        widget.config(bg=t['primary'], fg='white', activebackground=t['primary_hover'], activeforeground='white', relief='flat', borderwidth=0, padx=18, pady=6)
    elif widget_type == 'entry':
        widget.config(bg=t['input_bg'], fg=t['input_text'], insertbackground=t['accent'], relief='flat', borderwidth=1, highlightbackground=t['border'], highlightcolor=t['input_focus'], highlightthickness=1)
    elif widget_type == 'label':
        widget.config(bg=t['bg_medium'], fg=t['text_primary'])
    elif widget_type == 'frame':
        widget.config(bg=t['bg_medium'])
    elif widget_type == 'text':
        widget.config(bg=t['log_bg'], fg=t['text_primary'], insertbackground=t['accent'], relief='flat', borderwidth=0, padx=12, pady=12)
    elif widget_type == 'checkbutton':
        widget.config(bg=t['bg_dark'], fg=t['text_primary'], selectcolor=t['bg_dark'], activebackground=t['bg_dark'], activeforeground=t['text_primary'], relief='flat', borderwidth=0)


__all__ = ['THEME', 'get_theme', 'apply_theme_to_widget']
 
 
# Backward-compatible alias for agent_debugger.py
PINK_THEME = THEME
