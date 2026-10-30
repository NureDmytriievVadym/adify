<script lang="ts">
  import { tick } from 'svelte';
  import { goto } from '$app/navigation';
  import Icon from '#lib/components/Icon.svelte';
  import { session, signIn } from '#lib/accounts/session.svelte.ts';

  let email = $state('');
  let password = $state('');
  let message = $state('');
  let submitting = $state(false);
  let alert: HTMLParagraphElement | undefined = $state();

  $effect(() => {
    if (session.account) goto('/account', { replaceState: true });
  });

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    message = '';
    if (!email.trim() || !password) {
      message = 'Enter your email address and password.';
    } else {
      submitting = true;
      const result = await signIn(email, password);
      submitting = false;
      if (result.ok) return;
      message = result.message;
    }
    await tick();
    alert?.focus();
  }
</script>

<svelte:head
  ><title>Sign in — Adify</title><meta
    name="description"
    content="Sign in to your Adify account with your email address and password."
  /></svelte:head
>

<div class="container page-content register-page">
  <div class="page-intro">
    <span class="eyebrow">WELCOME BACK</span>
    <h1>Sign in to<br /><span>Adify.</span></h1>
    <p>Use the email address and password you registered with.</p>
  </div>

  <form class="register-card" novalidate onsubmit={submit}>
    {#if message}
      <p class="form-alert" role="alert" tabindex="-1" bind:this={alert}>{message}</p>
    {/if}

    <div class="form-field">
      <label for="email">Email address</label>
      <input id="email" name="email" type="email" autocomplete="email" bind:value={email} />
    </div>

    <div class="form-field">
      <label for="password">Password</label>
      <input
        id="password"
        name="password"
        type="password"
        autocomplete="current-password"
        bind:value={password}
      />
    </div>

    <button class="button button-dark register-submit" type="submit" disabled={submitting}>
      {submitting ? 'Signing in…' : 'Sign in'}
      <Icon name="arrow" />
    </button>
    <p class="form-footnote">New to Adify? <a href="/register">Create an account</a></p>
  </form>
</div>
