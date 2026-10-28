<script lang="ts">
  let { inverse = false }: { inverse?: boolean } = $props();
</script>

<a href="/" class:inverse class="brand" aria-label="Adify home">
  <span class="brand-mark" aria-hidden="true"
    ><svg viewBox="0 0 32 32" fill="none"
      ><path d="M6 24 16 6l10 18h-7l-3-6-3 6Z" fill="currentColor" /></svg
    ></span
  >
  <span>adify<span class="brand-dot">.</span></span>
</a>
