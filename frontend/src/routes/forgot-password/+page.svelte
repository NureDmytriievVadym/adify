<script lang="ts">
  import { tick } from 'svelte';
  import Icon from '#lib/components/Icon.svelte';
  import { requestPasswordReset } from '#lib/accounts/password-reset.ts';

  let email = $state('');
  let message = $state('');
  let sentTo = $state('');
  let submitting = $state(false);
  let alert: HTMLParagraphElement | undefined = $state();

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    message = '';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      message = 'Enter a valid email address.';
    } else {
      submitting = true;
      const result = await requestPasswordReset(email);
      submitting = false;
      if (result.ok) {
        sentTo = email.trim();
        return;
      }
      message = result.message;
    }
    await tick();
    alert?.focus();
  }
</script>

<svelte:head
  ><title>Forgot password — Adify</title><meta
    name="description"
    content="Get a link to set a new Adify password."
  /></svelte:head
>

<div class="container page-content register-page">
  <div class="page-intro">
    <span class="eyebrow">ACCOUNT RECOVERY</span>
    <h1>Forgot your<br /><span>password?</span></h1>
    <p>Enter your verified email address and we will send you a link to set a new password.</p>
  </div>

  {#if sentTo}
    <section class="register-card register-success" role="status" aria-labelledby="sent-title">
      <span class="success-mark" aria-hidden="true"><Icon name="check" size={22} /></span>
      <h2 id="sent-title">Check your email.</h2>
      <p>
        If <strong>{sentTo}</strong> belongs to an Adify account with a verified email, a reset link is
        on its way. The link works once and expires soon.
      </p>
      <a class="button button-dark" href="/sign-in">Back to sign in <Icon name="arrow" /></a>
    </section>
  {:else}
    <form class="register-card" novalidate onsubmit={submit}>
      {#if message}
        <p class="form-alert" role="alert" tabindex="-1" bind:this={alert}>{message}</p>
      {/if}

      <div class="form-field">
        <label for="email">Email address</label>
        <input id="email" name="email" type="email" autocomplete="email" bind:value={email} />
      </div>

      <button class="button button-dark register-submit" type="submit" disabled={submitting}>
        {submitting ? 'Sending…' : 'Send reset link'}
        <Icon name="arrow" />
      </button>
      <p class="form-footnote">Remembered it? <a href="/sign-in">Sign in</a></p>
    </form>
  {/if}
</div>
