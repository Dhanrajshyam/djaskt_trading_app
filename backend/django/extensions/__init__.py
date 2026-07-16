"""Infrastructure extensions for the Djaskt Django ledger service.

Cross-cutting integrations that sit outside the `ledger` app's domain
(e.g. secrets management) live here. Currently contains `vault.py`, the
Infisical Vault client used by `django_app/settings.py` to source secrets.
"""
