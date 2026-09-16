# System Design Interview Topics

## Scalability Fundamentals

### Load Balancing
Distributes incoming network requests across multiple servers. Types include round-robin, least connections, and IP hash. Important for high availability.

### Caching
Storing frequently accessed data in fast storage (memory/Redis) to reduce database load. Strategies: write-through, write-behind, cache-aside. Cache invalidation is one of the hard problems in CS.

### Database Sharding
Horizontal partitioning of data across multiple database instances. Helps with write scalability. Shard key selection is critical for even distribution.

### CDN (Content Delivery Network)
Distributes static content to edge locations closer to users. Reduces latency and offloads origin servers.

## High-Tradeoffs

### Consistency vs Availability vs Partition Tolerance
The CAP theorem states you can only guarantee two of three: Consistency, Availability, Partition tolerance. Most systems choose AP (availability + partition) with eventual consistency.

### Latency vs Throughput
Low latency prioritizes fast response times for individual requests. High throughput prioritizes processing many requests. Trade-off via batching, parallelism, and caching.

## Common Interview Questions

**Design a URL shortener:** Consider hash collisions, database schema, expiration, analytics.
**Design a message queue:** Consider ordering, delivery guarantees, durability, dead letter queues.
**Design a cache:** Consider eviction policies (LRU, LFU), consistency, invalidation.
**Design a rate limiter:** Fixed window, sliding window, token bucket algorithms.
**Design a notification system:** Fan-out strategies, real-time delivery (WebSockets), offline storage.
