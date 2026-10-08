"""Mailbox Adapters, one folder per Connection Method. Each folder's `adapter` module
registers its class with `@adapter(...)`, and the Mailbox Registry finds it by discovery
(`base.discover`), so nothing needs importing here.
"""
