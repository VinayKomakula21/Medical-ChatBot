import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import type { Settings as SettingsType } from '@/types';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';

interface SettingsProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  settings: SettingsType;
  onSettingsChange: (settings: SettingsType) => void;
}

export function Settings({ open, onOpenChange, settings, onSettingsChange }: SettingsProps) {
  const handleTemperatureChange = (value: number[]) => {
    onSettingsChange({ ...settings, temperature: value[0] });
  };

  const handleMaxTokensChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value);
    if (!isNaN(value) && value >= 50 && value <= 2048) {
      onSettingsChange({ ...settings, maxTokens: value });
    }
  };

  const handleStreamModeChange = (checked: boolean) => {
    onSettingsChange({ ...settings, streamMode: checked });
  };

  const resetDefaults = () => {
    onSettingsChange({
      temperature: 0.5,
      maxTokens: 512,
      streamMode: false,
      theme: 'system',
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Configure your chat preferences and model parameters.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="general" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="general">General</TabsTrigger>
            <TabsTrigger value="model">Model</TabsTrigger>
          </TabsList>

          <TabsContent value="general" className="space-y-4 mt-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="stream-mode">Streaming Mode</Label>
                <p className="text-sm text-muted-foreground">
                  Enable real-time streaming responses
                </p>
              </div>
              <Switch
                id="stream-mode"
                checked={settings.streamMode}
                onCheckedChange={handleStreamModeChange}
              />
            </div>
          </TabsContent>

          <TabsContent value="model" className="space-y-4 mt-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="temperature">Temperature</Label>
                <span className="text-sm text-muted-foreground">
                  {settings.temperature.toFixed(1)}
                </span>
              </div>
              <Slider
                id="temperature"
                min={0}
                max={1}
                step={0.1}
                value={[settings.temperature]}
                onValueChange={handleTemperatureChange}
              />
              <p className="text-xs text-muted-foreground">
                Controls randomness: 0 = focused, 1 = creative
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="max-tokens">Max Tokens</Label>
              <Input
                id="max-tokens"
                type="number"
                min={50}
                max={2048}
                value={settings.maxTokens}
                onChange={handleMaxTokensChange}
              />
              <p className="text-xs text-muted-foreground">
                Maximum length of the response (50-2048)
              </p>
            </div>
          </TabsContent>
        </Tabs>

        <div className="flex justify-between pt-4">
          <Button variant="outline" onClick={resetDefaults}>
            Reset to Defaults
          </Button>
          <Button onClick={() => onOpenChange(false)}>
            Done
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}