{# Template for rendering towncrier news fragments into the changelog. #}
{# #}
{# Fragments should be one of: #}
{#   - Added for new features. #}
{#   - Changed for changes in existing functionality. #}
{#   - Deprecated for soon-to-be removed features. #}
{#   - Removed for now removed features. #}
{#   - Fixed for any bug fixes. #}
{#   - Security in case of vulnerabilities. #}
{# #}
{# Sections are automatically grouped by type (e.g., Added, Changed, Fixed). #}
{% if sections %}
{% for section, items in sections.items() %}
### {{ section }}

{% for item in items %}
- {{ item }}

{% endfor %}
{% endfor %}
{% else %}
No significant changes.
{% endif %}
