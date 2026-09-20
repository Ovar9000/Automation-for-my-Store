---
name: svelte-5-runes
description: Comprehensive guide and best practices for developing Svelte 5 applications using Runes ($state, $derived, $effect, $props, $bindable). Use whenever authoring, refactoring, or auditing Svelte 5 code to ensure modern signal-based reactivity without Svelte 4 legacy constructs.
---

# Svelte 5 Runes Best Practices & Architecture Guide

Svelte 5 introduces an explicit, signal-based reactivity model called **Runes**. This replaces the compiler-magic reactivity of Svelte 3/4 (such as `let` for local state, `$:` for reactive statements, and `export let` for props).

---

## 1. Core Runes Reference

### `$state(initialValue)`
Declares reactive state.
- Objects and arrays are made deeply reactive via fine-grained proxies.
- Mutating an array (`array.push(...)`) or an object property (`user.name = '...'`) automatically triggers granular UI updates.
- For large static datasets where you don't need deep proxying, use `$state.raw(...)`.

```svelte
<script lang="ts">
  let count = $state(0);
  let user = $state({ name: 'Maria', age: 28 });
  let items = $state<string[]>([]);

  function addItem(item: string) {
    items.push(item); // Deep reactivity automatically tracks array mutations!
  }
</script>
```

### `$derived(expression)` & `$derived.by(() => ...)`
Creates a read-only computed value that updates only when its dependencies change.
- Use `$derived(...)` for single expressions.
- Use `$derived.by(() => { ... })` for multi-step logic, conditions, or loops.

```svelte
<script lang="ts">
  let price = $state(50);
  let qty = $state(2);

  // Single expression
  let subtotal = $derived(price * qty);

  // Multi-step computation
  let discount = $derived.by(() => {
    if (qty >= 10) return subtotal * 0.1;
    if (qty >= 5) return subtotal * 0.05;
    return 0;
  });
</script>
```

### `$props()`
Replaces Svelte 4's `export let`.
- Used to declare component props with TypeScript typing and default values.
- To create two-way bound props, use `$bindable()`.

```svelte
<script lang="ts">
  interface Props {
    title: string;
    isActive?: boolean;
    count?: number;
    onSelect?: (val: string) => void;
  }

  let { title, isActive = false, count = $bindable(0), onSelect }: Props = $props();
</script>
```

### `$effect(() => ...)`
Manages side effects (DOM interactions, intervals, event listeners, syncing to storage).
- Automatically tracks all reactive variables read inside the function body.
- Return a cleanup function to clean up listeners or timers.
- Avoid using `$effect` to update state that could be expressed as a `$derived` value.

```svelte
<script lang="ts">
  let text = $state('');

  $effect(() => {
    console.log('Text changed:', text);
    const timer = setTimeout(() => { ... }, 300);
    return () => clearTimeout(timer); // Cleanup on dependency change or unmount
  });
</script>
```

---

## 2. Universal Reactivity in `.svelte.ts` Files

In Svelte 5, runes can be used **outside of components** in `.svelte.ts` (or `.svelte.js`) files.
This completely replaces the need for Svelte 4 `writable()` / `readable()` stores!

```typescript
// cart.svelte.ts
class CartStore {
  items = $state<CartItem[]>([]);
  total = $derived(this.items.reduce((sum, i) => sum + i.price * i.qty, 0));

  addItem(item: CartItem) {
    this.items.push(item);
  }

  removeItem(id: string) {
    this.items = this.items.filter(i => i.id !== id);
  }
}

export const cart = new CartStore();
```

---

## 3. Strict Rules: Banned Svelte 4 Constructs

When authoring or reviewing Svelte 5 code, **NEVER** use the following legacy patterns:

| ❌ Clunky Svelte 4 Legacy Pattern | ✅ Modern Svelte 5 Runes Equivalent |
| :--- | :--- |
| `export let prop = 'default'` | `let { prop = 'default' }: Props = $props()` |
| `$: computed = a + b` | `let computed = $derived(a + b)` |
| `$: if (a) doSomething()` | `$effect(() => { if (a) doSomething(); })` |
| `on:click={handler}` | `onclick={handler}` (native DOM attributes) |
| `on:keydown={handler}` | `onkeydown={handler}` |
| `const dispatch = createEventDispatcher()` | Pass callback props: `let { onSelect }: Props = $props()` |
| `writable(0)` / `$store` | Class with `$state` inside `.svelte.ts` |
| `<slot />` / `<slot name="header" />` | `{#snippet children()}` / `{@render children()}` |

---

## 4. Critical Pitfalls to Avoid

1. **Reactivity Loss via Destructuring**:
   ```typescript
   // ❌ BAD: Destructuring breaks reactive proxy link
   let { name, price } = $state({ name: 'Rice', price: 50 });
   
   // ✅ GOOD: Keep the object reference
   let product = $state({ name: 'Rice', price: 50 });
   // Read via product.name, product.price
   ```

2. **Event Naming**:
   Always use standard lowercase event attributes (`onclick`, `oninput`, `onkeydown`) instead of `on:click`.

3. **Function vs Derived**:
   If a computation is cheap and only used in a template once, a normal function or inline expression is fine. Use `$derived` when the value is cached or referenced across multiple reactive dependencies.
