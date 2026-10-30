<script lang="ts">
  import '@fontsource/dm-sans/latin-400.css';
  import '@fontsource/dm-sans/latin-500.css';
  import '@fontsource/dm-sans/latin-600.css';
  import '@fontsource/dm-sans/latin-700.css';
  import '../app.css';
  import Header from '#lib/components/Header.svelte';
  import Footer from '#lib/components/Footer.svelte';
  import { onMount } from 'svelte';
  import { restoreSession } from '#lib/accounts/session.svelte.ts';
  let { children } = $props();
  onMount(restoreSession);
</script>

<a class="skip-link" href="#main-content">Skip to content</a>
<Header />
<main id="main-content" tabindex="-1">{@render children()}</main>
<Footer />
