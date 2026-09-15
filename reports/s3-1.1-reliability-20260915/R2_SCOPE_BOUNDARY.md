# R2 single-source scope boundary

R2 deliberately covers deterministic single-source generation only.

The frozen R0 worker request transports one source byte string. Multi-source module/import campaigns therefore require a future source-bundle transport contract rather than an ad-hoc extension inside the generator.

This deferral does not remove module/import support from S3 1.0. It only prevents R2 from inventing a second, unfrozen transport format.

```text
R2_SINGLE_SOURCE_GENERATION=YES
R2_MODULE_LANGUAGE_SUPPORT_REMOVED=NO
R2_MULTI_SOURCE_CAMPAIGN_TRANSPORT=DEFERRED_CONTRACT_REQUIRED
R2_HIDDEN_PROTOCOL_EXTENSION=NO
```
