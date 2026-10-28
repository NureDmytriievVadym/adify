<script lang="ts">
  import Brand from './Brand.svelte';
  import Icon from './Icon.svelte';
</script>

<footer class="site-footer">
  <div class="container">
    <div class="footer-main">
      <div>
        <Brand inverse />
        <p>A better place to find your<br />next advertising partnership.</p>
      </div>
      <div class="footer-links">
        <h2>Explore</h2>
        <a href="/listings">Marketplace</a><a href="/how-it-works">How it works</a><a href="/orders"
          >Orders preview</a
        >
      </div>
      <div class="footer-note">
        <span class="eyebrow">Built for connections</span>
        <p>For the brands with a story.<br />And the people who can share it.</p>
        <span class="footer-location"><Icon name="globe" size={16} /> Ukraine · English · UAH</span>
      </div>
    </div>
    <div class="footer-bottom">
      <span>© {new Date().getFullYear()} Adify</span><span>Website preview · Sample content</span
      ><span>Policies will be published before launch.</span>
    </div>
  </div>
</footer>
