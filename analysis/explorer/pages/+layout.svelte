<script>
	// Layout override: UCT branding in the header instead of the Evidence
	// wordmark (static/uct-{light,dark}.svg, UCT brand colours Pantone
	// 2925 C #009ADA / 539 C #00243A). The "Built with Evidence" footer
	// link is deliberately kept (builtWithEvidence defaults to true).
	import '@evidence-dev/tailwind/fonts.css';
	import '../app.css';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	export let data;
</script>

<EvidenceDefaultLayout {data} lightLogo="/uct-light.svg" darkLogo="/uct-dark.svg">
	<slot slot="content" />
</EvidenceDefaultLayout>
