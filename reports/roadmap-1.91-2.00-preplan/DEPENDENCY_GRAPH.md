# M1.91-M2.00 Dependency Graph

```text
M1.81-M1.90 publication
          |
        M1.91
          |
        M1.92
        /   \
     M1.93  M1.95
       |      |
     M1.94  M1.96
        \    /
         M1.97
           |
         M1.98
           |
         M1.99
           |
         M2.00
```

M1.93 and M1.95 can be planned in parallel after M1.92, but each still has a
separate branch and merge. M1.94 consumes the streaming boundary. M1.96
consumes registry v2 and the M1.87 signature boundary. M1.97 consumes the
target contracts from M1.88-M1.90. M1.98 unifies the native matrix before M1.99
optimization. M2.00 is a release gate over the complete merged history.

No edge authorizes implementation before the predecessor is merged and its
entry criteria are satisfied.
