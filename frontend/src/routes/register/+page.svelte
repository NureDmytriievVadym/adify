<script lang="ts">
  import { tick } from 'svelte';
  import Icon from '#lib/components/Icon.svelte';
  import {
    registerAccount,
    validateRegistration,
    type Account,
    type FieldErrors,
    type RegistrationField,
    type RegistrationInput,
  } from '#lib/accounts/registration.ts';

  const order: RegistrationField[] = ['role', 'display_name', 'email', 'phone', 'password'];
  const roles = [
    {
      value: 'customer',
      title: 'Customer',
      description: 'Find placements and order advertising for your brand.',
    },
    {
      value: 'provider',
      title: 'Provider',
      description: 'Offer your advertising space or services to customers.',
    },
  ] as const;

  let input: RegistrationInput = $state({
    display_name: '',
    email: '',
    phone: '',
    role: '',
    password: '',
  });
  let errors: FieldErrors = $state({});
  let message = $state('');
  let submitting = $state(false);
  let account: Account | null = $state(null);
  let form: HTMLFormElement | undefined = $state();

  const describedBy = (field: RegistrationField, hint = false) =>
    [hint && `${field}-hint`, errors[field] && `${field}-error`].filter(Boolean).join(' ') ||
    undefined;

  async function focusFirstError() {
    await tick();
    const field = order.find((name) => errors[name]);
    if (field) form?.querySelector<HTMLInputElement>(`[name="${field}"]`)?.focus();
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    message = '';
    errors = validateRegistration(input);
    if (Object.keys(errors).length > 0) return focusFirstError();

    submitting = true;
    const result = await registerAccount(input);
    submitting = false;
    if (result.ok) {
      account = result.account;
      return;
    }
    errors = result.fieldErrors;
    message = result.message ?? '';
    await focusFirstError();
  }
</script>

<svelte:head
  ><title>Create an account — Adify</title><meta
    name="description"
    content="Register a customer or provider account on Adify, the internet advertising marketplace for Ukraine."
  /></svelte:head
>

<div class="container page-content register-page">
  <div class="page-intro">
    <span class="eyebrow">JOIN ADIFY</span>
    <h1>Create your<br /><span>Adify account.</span></h1>
    <p>One account, one role. Choose whether you buy or offer advertising.</p>
  </div>

  {#if account}
    <section class="register-card register-success" role="status" aria-labelledby="success-title">
      <span class="success-mark" aria-hidden="true"><Icon name="check" size={22} /></span>
      <h2 id="success-title">Welcome, {account.display_name}.</h2>
      <p>
        Your {account.role} account for <strong>{account.email}</strong> has been created. Verify your
        email address and phone number to reveal phone numbers, start chats, create listings, and place
        orders. Sign-in and verification are coming in a later release.
      </p>
      <a class="button button-dark" href="/listings">Browse the marketplace <Icon name="arrow" /></a
      >
    </section>
  {:else}
    <form class="register-card" novalidate bind:this={form} onsubmit={submit}>
      {#if message}
        <p class="form-alert" role="alert">{message}</p>
      {/if}

      <fieldset
        class="role-options"
        class:invalid={errors.role}
        aria-describedby={describedBy('role')}
      >
        <legend>I want to join as</legend>
        {#each roles as role (role.value)}
          <label class="role-option">
            <input type="radio" name="role" value={role.value} bind:group={input.role} />
            <span class="role-title">{role.title}</span>
            <span class="role-description">{role.description}</span>
          </label>
        {/each}
        {#if errors.role}<p class="field-error" id="role-error">{errors.role}</p>{/if}
      </fieldset>

      <div class="form-field">
        <label for="display_name">Display name</label>
        <input
          id="display_name"
          name="display_name"
          autocomplete="nickname"
          maxlength="100"
          bind:value={input.display_name}
          aria-invalid={errors.display_name ? 'true' : undefined}
          aria-describedby={describedBy('display_name')}
        />
        {#if errors.display_name}
          <p class="field-error" id="display_name-error">{errors.display_name}</p>
        {/if}
      </div>

      <div class="form-field">
        <label for="email">Email address</label>
        <input
          id="email"
          name="email"
          type="email"
          autocomplete="email"
          bind:value={input.email}
          aria-invalid={errors.email ? 'true' : undefined}
          aria-describedby={describedBy('email', true)}
        />
        <p class="field-hint" id="email-hint">Used to sign in. Never shown to other users.</p>
        {#if errors.email}<p class="field-error" id="email-error">{errors.email}</p>{/if}
      </div>

      <div class="form-field">
        <label for="phone">Phone number</label>
        <input
          id="phone"
          name="phone"
          type="tel"
          autocomplete="tel"
          placeholder="+380671234567"
          bind:value={input.phone}
          aria-invalid={errors.phone ? 'true' : undefined}
          aria-describedby={describedBy('phone', true)}
        />
        <p class="field-hint" id="phone-hint">A Ukrainian number starting with +380.</p>
        {#if errors.phone}<p class="field-error" id="phone-error">{errors.phone}</p>{/if}
      </div>

      <div class="form-field">
        <label for="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          autocomplete="new-password"
          bind:value={input.password}
          aria-invalid={errors.password ? 'true' : undefined}
          aria-describedby={describedBy('password', true)}
        />
        <p class="field-hint" id="password-hint">
          At least 8 characters, including a letter and a digit.
        </p>
        {#if errors.password}<p class="field-error" id="password-error">{errors.password}</p>{/if}
      </div>

      <button class="button button-dark register-submit" type="submit" disabled={submitting}>
        {submitting ? 'Creating account…' : 'Create account'}
        <Icon name="arrow" />
      </button>
    </form>
  {/if}
</div>
