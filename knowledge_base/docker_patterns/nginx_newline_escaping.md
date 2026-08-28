# Nginx Configuration Generation: Newline Escaping Bug

## Context
When an automated agent or script generates an Nginx configuration file (`nginx.conf`) for an API Gateway, it might use string manipulation or template rendering to construct the output.

## The Problem
A common bug occurs when generating consecutive configuration blocks (like multiple `upstream` blocks). The generator might incorrectly output the literal string `chr(10)` instead of a proper newline character (`\n`). 

Nginx does not recognize `chr(10)` as a configuration directive, causing it to immediately crash on startup with an error similar to:
```
[emerg] 1#1: unknown directive "chr(10)" in /etc/nginx/conf.d/default.conf:6
```

Example of a generated configuration with this bug:
```nginx
    upstream usermanagement {
        server usermanagement:8000;
    }chr(10)    upstream orderprocessing {
        server orderprocessing:8000;
    }
```

## The Solution
When generating or modifying Nginx configuration files, **always ensure proper newline characters (`\n`) are used** to separate blocks and directives. Never use literal strings like `chr(10)`.

### Correct Pattern
```nginx
    upstream usermanagement {
        server usermanagement:8000;
    }

    upstream orderprocessing {
        server orderprocessing:8000;
    }
```

Agents writing configuration files must verify that whitespace and line breaks are correctly serialized as literal formatting in the final file output, avoiding any raw character codes.
