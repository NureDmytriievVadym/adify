<script lang="ts">
  import { page } from '$app/state';
  import { afterNavigate } from '$app/navigation';
  import Brand from './Brand.svelte';
  import Icon from './Icon.svelte';
  import { session } from '#lib/accounts/session.svelte.ts';

  let open = $state(false);
  afterNavigate(() => {
    open = false;
  });
  const links = [
    { href: '/listings', label: 'Marketplace' },
    { href: '/how-it-works', label: 'How it works' },
    { href: '/orders', label: 'Orders preview' },
  ];
</script>

<svelte:window
  onkeydown={(event) => {
    if (event.key === 'Escape') open = false;
  }}
/>

<header class="site-header">
  <div class="container header-inner">
    <Brand />
    <button
      class="menu-toggle"
      type="button"
      aria-expanded={open}
      aria-controls="main-navigation"
      aria-label={open ? 'Close navigation' : 'Open navigation'}
      onclick={() => {
        open = !open;
      }}><Icon name={open ? 'close' : 'menu'} /></button
    >
    <nav id="main-navigation" class:open aria-label="Main navigation">
      <div class="nav-links">
        {#each links as link (link.href)}
          <a
            href={link.href}
            aria-current={page.url.pathname.startsWith(link.href) ? 'page' : undefined}
            >{link.label}</a
          >
        {/each}
      </div>
      <div class="header-actions">
        <span class="currency-label">Ukraine <span aria-hidden="true">·</span> UAH</span>
        {#if session.account}
          <a class="sign-in-link" href="/listings/mine">My listings</a>
          <a class="sign-in-link" href="/listings/new">New listing</a>
          <a class="button button-dark button-small" href="/account"
            >My account <Icon name="arrow" size={16} /></a
          >
        {:else}
          <a class="sign-in-link" href="/sign-in">Sign in</a>
          <a class="button button-dark button-small" href="/register"
            >Get started <Icon name="arrow" size={16} /></a
          >
        {/if}
      </div>
    </nav>
  </div>
</header>
