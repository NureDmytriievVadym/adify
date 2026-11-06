<script lang="ts">
  import { tick } from 'svelte';
  import { page } from '$app/state';
  import Icon from '#lib/components/Icon.svelte';
  import { resetPassword } from '#lib/accounts/password-reset.ts';
  import { passwordError } from '#lib/accounts/registration.ts';

  const token = $derived(page.url.searchParams.get('token') ?? '');

  let password = $state('');
  let fieldError = $state('');
  let message = $state('');
  let done = $state(false);
  let submitting = $state(false);
  let alert: HTMLParagraphElement | undefined = $state();

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    message = '';
    fieldError = passwordError(password) ?? '';
    if (fieldError) return;
    submitting = true;
    const result = await resetPassword(token, password);
    submitting = false;
    if (result.ok) {
      done = true;
      return;
    }
    message = result.message;
    await tick();
    alert?.focus();
  }
</script>

<svelte:head
  ><title>Set a new password — Adify</title><meta
    name="description"
    content="Set a new password for your Adify account."
  /></svelte:head
>

<div class="container page-content register-page">
  <div class="page-intro">
    <span class="eyebrow">ACCOUNT RECOVERY</span>
    <h1>Set a new<br /><span>password.</span></h1>
    <p>Choose a new password for your Adify account.</p>
  </div>

  {#if done}
    <section class="register-card register-success" role="status" aria-labelledby="done-title">
      <span class="success-mark" aria-hidden="true"><Icon name="check" size={22} /></span>
      <h2 id="done-title">Password changed.</h2>
      <p>Sign in with your new password. You have been signed out everywhere else.</p>
      <a class="button button-dark" href="/sign-in">Sign in <Icon name="arrow" /></a>
    </section>
  {:else if !token}
    <section class="register-card" aria-labelledby="missing-title">
      <h2 id="missing-title">This link is incomplete.</h2>
      <p>Open the link from the email again, or request a new one.</p>
      <a class="button button-dark" href="/forgot-password"
        >Request a new link <Icon name="arrow" /></a
      >
    </section>
  {:else}
    <form class="register-card" novalidate onsubmit={submit}>
      {#if message}
        <p class="form-alert" role="alert" tabindex="-1" bind:this={alert}>
          {message}
          <a href="/forgot-password">Request a new link</a>
        </p>
      {/if}

      <div class="form-field">
        <label for="password">New password</label>
        <input
          id="password"
          name="password"
          type="password"
          autocomplete="new-password"
          aria-invalid={fieldError ? 'true' : undefined}
          aria-describedby={fieldError ? 'password-error password-hint' : 'password-hint'}
          bind:value={password}
        />
        <p class="field-hint" id="password-hint">
          At least 8 characters, including a letter and a digit.
        </p>
        {#if fieldError}<p class="field-error" id="password-error">{fieldError}</p>{/if}
      </div>

      <button class="button button-dark register-submit" type="submit" disabled={submitting}>
        {submitting ? 'Saving…' : 'Set new password'}
        <Icon name="arrow" />
      </button>
    </form>
  {/if}
</div>
